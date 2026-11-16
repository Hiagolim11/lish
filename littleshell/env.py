"""Every environment variable Little Shell reads, in one place.

Each is optional; the default is what the app uses when it is unset. These are
power-user and testing knobs, not part of the normal UI. Read them through the
helpers below so names and parsing stay consistent.

Knobs a user may set:
  LISH_FONT               override the terminal font family
  LISH_AUDIO_SINK         GStreamer sink for key sounds (e.g. fakesink in tests)
  LISH_SHELL_INTEGRATION  "0" disables the zsh/bash prompt hooks
  LISH_SPEECH_MODEL       Whisper model for dictation (default: base)
  LISH_SPEECH_SECONDS     dictation recording length in seconds (default: 8)
  LISH_GUI_TEST           "1" runs the headless GUI smoke suite

Set by the app for its own child processes (not user knobs):
  LISH_SEPARATE   run as a separate instance instead of the single-process server
  LISH_SOCKET     path to the viewer's unix socket, passed to panes
  LISH_PANE       the pane id a `lish-open` call belongs to
  LISH_ZDOTDIR    the user's real ZDOTDIR, preserved across the zsh integration
"""
from __future__ import annotations

import os

SEPARATE = "LISH_SEPARATE"
FONT = "LISH_FONT"
AUDIO_SINK = "LISH_AUDIO_SINK"
SHELL_INTEGRATION = "LISH_SHELL_INTEGRATION"
SPEECH_MODEL = "LISH_SPEECH_MODEL"
SPEECH_SECONDS = "LISH_SPEECH_SECONDS"
GUI_TEST = "LISH_GUI_TEST"

_TRUE = ("1", "true", "yes", "on")


def flag(name: str, default: bool = False) -> bool:
    """A boolean knob: unset → default, otherwise true for 1/true/yes/on."""
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in _TRUE


def text(name: str, default: str | None = None) -> str | None:
    """A string knob: the value, or default when unset or empty."""
    return os.environ.get(name) or default


def number(name: str, default: int, minimum: int | None = None) -> int:
    """An integer knob, clamped to ``minimum`` when given; default on garbage."""
    try:
        value = int(os.environ.get(name) or default)
    except ValueError:
        value = default
    return max(minimum, value) if minimum is not None else value
