"""Dictation without a window: record, transcribe, type into the terminal.

One shortcut (or the microphone button) starts it: it records a few seconds
from the microphone — a countdown shows in the status bar — then stops on its
own (or earlier if you press the shortcut again), transcribes with a local
Whisper model, and feeds the text into the active pane (no Enter, so you can
review it). There is no dialog. A single worker process stays alive and keeps
the model warm between dictations, so only the first one pays the load cost.
The first time it runs, the optional dependencies are checked and, if missing,
installed in the background — nothing to install by hand, no frozen interface.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from ..env import SPEECH_SECONDS, number
from ..runtime import GLib

PACKAGES = ["faster-whisper>=1.1,<2", "sounddevice>=0.5,<1", "numpy>=1.24,<3"]
ROOT = str(Path(__file__).resolve().parents[2])
MAX_SECONDS = number(SPEECH_SECONDS, 8, minimum=2)


class SpeechController:
    """Drives dictation for one window. State: idle, preparing, recording, busy."""

    def __init__(self, window):
        self.window = window
        self.state = "idle"
        self.ready = False
        self.process = None     # persistent worker, kept warm between dictations
        self.reader = None
        self.count_timer = 0
        self.remaining = 0

    # ------------------------------------------------------------------ status
    def say(self, text: str, transient: bool = False) -> None:
        status = getattr(self.window, "status", None)
        if status is not None:
            status.set_text(text)
            if transient:
                GLib.timeout_add(5000, self._clear, text)

    def _clear(self, text: str) -> bool:
        status = getattr(self.window, "status", None)
        if status is not None and status.get_text() == text:
            status.set_text("")
        return False

    def _mark_button(self, active: bool) -> None:
        button = getattr(self.window, "dictate_button", None)
        if button is not None:
            context = button.get_style_context()
            (context.add_class if active else context.remove_class)("recording")

    # ------------------------------------------------------------------ toggle
    def toggle(self) -> None:
        if self.state == "recording":
            self.stop()
        elif self.state == "idle":
            self.begin()
        # preparing / busy: ignore until it settles

    def begin(self) -> None:
        if self.ready:
            self.start_recording()
            return
        self.state = "preparing"
        self.say("Preparando o ditado (primeira vez pode demorar)…")
        threading.Thread(target=self._prepare, daemon=True).start()

    # ------------------------------------------------------------- dependencies
    def _prepare(self) -> None:
        ok = self.have_deps()
        if not ok:
            ok = self._install() and self.have_deps()
        GLib.idle_add(self._prepared, ok)

    def _prepared(self, ok: bool) -> bool:
        if ok:
            self.ready = True
            self.start_recording()
        else:
            self.state = "idle"
            self.say("Não consegui preparar o ditado (dependências de fala). Veja requirements-speech.txt.",
                     transient=True)
        return False

    @staticmethod
    def have_deps() -> bool:
        try:
            return subprocess.run(
                [sys.executable, "-c", "import faster_whisper, sounddevice, numpy"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _install(self) -> bool:
        try:
            return subprocess.run(
                [sys.executable, "-m", "pip", "install", "--break-system-packages", *PACKAGES],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    # --------------------------------------------------------- the warm worker
    def _worker_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _ensure_worker(self) -> bool:
        if self._worker_alive():
            return True
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "littleshell.speech"], cwd=ROOT,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1,
            )
        except OSError as error:
            self.process = None
            self.say(f"Não foi possível iniciar o ditado: {error}", transient=True)
            return False
        self.reader = threading.Thread(target=self._read_results, args=(self.process,), daemon=True)
        self.reader.start()
        return True

    def _read_results(self, process) -> None:
        for line in process.stdout:
            line = line.strip()
            if line:
                GLib.idle_add(self._on_result, line)
        GLib.idle_add(self._on_worker_gone, process)

    def _send(self, command: str) -> bool:
        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            return True
        except (OSError, ValueError, AttributeError):
            self.process = None
            self.state = "idle"
            self.say("O ditado caiu; tente de novo.", transient=True)
            return False

    # --------------------------------------------------------------- recording
    def start_recording(self) -> None:
        if not self._ensure_worker() or not self._send("record"):
            self.state = "idle"
            return
        self.state = "recording"
        self._mark_button(True)
        self.remaining = MAX_SECONDS
        self.say(f"🎤 Gravando… {self.remaining}s · Ctrl+Shift+M para parar")
        self.count_timer = GLib.timeout_add(1000, self._tick)

    def _tick(self) -> bool:
        if self.state != "recording":
            self.count_timer = 0
            return False
        self.remaining -= 1
        if self.remaining <= 0:
            self.count_timer = 0
            self.stop()
            return False
        self.say(f"🎤 Gravando… {self.remaining}s · Ctrl+Shift+M para parar")
        return True

    def stop(self) -> None:
        if self.state != "recording":
            return
        self.state = "busy"
        self._mark_button(False)
        if self.count_timer:
            GLib.source_remove(self.count_timer)
            self.count_timer = 0
        self.say("Transcrevendo…")
        self._send("stop")

    def _on_result(self, line: str) -> bool:
        text, message = "", ""
        try:
            result = json.loads(line or "{}")
            if result.get("error") == "missing-deps":
                self.ready = False
                message = "Faltam dependências de fala; serão instaladas no próximo uso."
            elif "error" in result:
                message = result["error"]
            else:
                text = (result.get("text") or "").strip()
                message = "" if text else "Nenhuma fala detectada — fale mais perto do microfone."
        except ValueError:
            message = "Falha ao transcrever."
        if self.state == "busy":
            self.state = "idle"
        if text:
            self.type_into_terminal(text)
        if message:
            self.say(message, transient=True)
        return False

    def _on_worker_gone(self, process) -> bool:
        if process is self.process:
            self.process = None
            if self.state in ("recording", "busy"):
                self.state = "idle"
                self.say("O ditado parou inesperadamente.", transient=True)
        return False

    def type_into_terminal(self, text: str) -> None:
        getter = getattr(self.window, "get_active_terminal", None)
        pane = getter() if getter is not None else None
        terminal = getattr(pane, "terminal", None)
        if terminal is not None:
            terminal.feed_child(text.replace("\n", " ").encode())

    # ------------------------------------------------------------------ cleanup
    def cleanup(self, *_) -> None:
        if self.count_timer:
            GLib.source_remove(self.count_timer)
            self.count_timer = 0
        if self.process is not None:
            try:
                self.process.stdin.close()  # closing stdin tells the worker to exit
            except (OSError, ValueError):
                pass
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                except (OSError, ProcessLookupError):
                    pass
            try:
                self.process.wait(timeout=2)
            except (subprocess.SubprocessError, OSError):
                try:
                    self.process.kill()
                except (OSError, ProcessLookupError):
                    pass
            self.process = None
        self.state = "idle"


__all__ = ["SpeechController"]
