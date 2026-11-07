"""Jump through the commands run in a pane.

It reads the pane's prompt marks (command, status, duration) that the shell
integration already records, lists them newest-first, and scrolls the
terminal to the one you pick. No new tracking — only a view over existing data.
"""
from __future__ import annotations

from ..runtime import Gdk, Gtk, Pango
from ..terminal import format_duration


class CommandNavigator(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window | None, pane) -> None:
        super().__init__(title="Comandos", transient_for=parent, modal=False)
        self.set_default_size(560, 460)
        self.pane = pane
        self.add_button("Fechar", Gtk.ResponseType.CLOSE)
        self.connect("response", lambda *_: self.destroy())
        self.connect("key-press-event", self._on_key)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-activated", self._activate)
        marks = [mark for mark in pane.prompts if mark.command.strip()]
        for mark in reversed(marks):  # newest first
            self.listbox.add(self._row(mark))
        if not marks:
            empty = Gtk.Label(label="Nenhum comando ainda.", xalign=0)
            empty.set_margin_top(16)
            empty.set_margin_start(16)
            self.listbox.add(empty)
        scroller.add(self.listbox)
        self.get_content_area().pack_start(scroller, True, True, 0)
        self.show_all()
        first = self.listbox.get_row_at_index(0)
        if first is not None:
            self.listbox.select_row(first)
            first.grab_focus()

    def _row(self, mark) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.mark = mark
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        for setter, value in (("start", 12), ("end", 12), ("top", 6), ("bottom", 6)):
            getattr(line, f"set_margin_{setter}")(value)
        ok = mark.exit_status in (0, None)
        badge = Gtk.Label(label="·" if not mark.finished else ("✓" if ok else "✗"))
        badge.get_style_context().add_class("status-ok" if ok else "status-warning")
        command = Gtk.Label(label=mark.command.strip(), xalign=0)
        command.set_ellipsize(Pango.EllipsizeMode.END)
        command.set_hexpand(True)
        meta = Gtk.Label(label=self._meta(mark), xalign=1)
        meta.get_style_context().add_class("status")
        line.pack_start(badge, False, False, 0)
        line.pack_start(command, True, True, 0)
        line.pack_end(meta, False, False, 0)
        row.add(line)
        return row

    @staticmethod
    def _meta(mark) -> str:
        parts = []
        if mark.exit_status not in (0, None):
            parts.append(f"saída {mark.exit_status}")
        if mark.duration:
            parts.append(format_duration(mark.duration))
        return " · ".join(parts)

    def _activate(self, _listbox, row) -> None:
        mark = getattr(row, "mark", None)
        if mark is not None:
            self.pane.scroll_to_row(mark.first_row)
            self.destroy()

    def _on_key(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False


__all__ = ["CommandNavigator"]
