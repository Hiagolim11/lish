import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from littleshell.runtime import GLib, Gtk
from littleshell.dialogs.speech import SpeechController


def fake_window():
    pane = SimpleNamespace(terminal=Mock())
    return SimpleNamespace(status=Gtk.Label(), get_active_terminal=lambda: pane), pane


def make_worker():
    worker = Mock()
    worker.poll.return_value = None  # alive
    worker.stdin = Mock()
    worker.wait.return_value = 0
    return worker


def drop_timer(controller):
    if controller.count_timer:
        GLib.source_remove(controller.count_timer)
        controller.count_timer = 0


class SpeechControllerTests(unittest.TestCase):
    @patch.object(SpeechController, "_read_results", lambda self, process: None)
    def test_record_stop_types_and_keeps_worker_warm(self):
        window, pane = fake_window()
        controller = SpeechController(window)
        controller.ready = True
        worker = make_worker()
        with patch("littleshell.dialogs.speech.subprocess.Popen", return_value=worker) as popen:
            controller.toggle()  # record
            self.assertEqual(controller.state, "recording")
            worker.stdin.write.assert_any_call("record\n")
            drop_timer(controller)

            controller.toggle()  # stop
            self.assertEqual(controller.state, "busy")
            worker.stdin.write.assert_any_call("stop\n")

            controller._on_result('{"text": "ls -la"}')
            pane.terminal.feed_child.assert_called_once_with(b"ls -la")
            self.assertEqual(controller.state, "idle")

            controller.toggle()  # a second dictation reuses the warm worker
            drop_timer(controller)
            self.assertEqual(popen.call_count, 1)  # no new process spawned
        controller.state = "idle"

    @patch.object(SpeechController, "_read_results", lambda self, process: None)
    def test_auto_stop_when_countdown_ends(self):
        window, _pane = fake_window()
        controller = SpeechController(window)
        controller.ready = True
        worker = make_worker()
        with patch("littleshell.dialogs.speech.subprocess.Popen", return_value=worker):
            controller.toggle()
            drop_timer(controller)
            controller.remaining = 1
            self.assertFalse(controller._tick())  # last tick stops
            self.assertEqual(controller.state, "busy")
            worker.stdin.write.assert_any_call("stop\n")

    @patch.object(SpeechController, "_read_results", lambda self, process: None)
    def test_cleanup_closes_stdin_and_terminates(self):
        window, _pane = fake_window()
        controller = SpeechController(window)
        controller.ready = True
        worker = make_worker()
        with patch("littleshell.dialogs.speech.subprocess.Popen", return_value=worker):
            controller.toggle()
        controller.cleanup()
        worker.stdin.close.assert_called_once()
        worker.terminate.assert_called_once()
        self.assertIsNone(controller.process)
        self.assertEqual(controller.state, "idle")


if __name__ == "__main__":
    unittest.main()
