from gi.repository import GLib, Gtk
from typing import TYPE_CHECKING

from tps_frontend import _

if TYPE_CHECKING:
    from tps_frontend.application import Application


class ErrorDialog(Gtk.MessageDialog):
    def __init__(
        self,
        app: "Application",
        title: str,
        msg: str,
        with_send_report_button: bool = True,
    ):
        super().__init__(
            app.window,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE,
            title,
            use_markup=True,
        )
        self.app = app
        self.title = title
        self.msg = msg

        message_area = self.get_message_area()  # type: Gtk.Box
        title_label, secondary_label = message_area.get_children()  # type: Gtk.Label

        # Make the title bold
        title = GLib.markup_escape_text(title)
        title_label.set_markup(f"<b>{title}</b>")

        # Make the error message selectable to allow the user to search
        # for the error via copy-and-paste.
        secondary_label.set_selectable(True)

        if with_send_report_button:
            error_report_msg = _(
                "You can send an error report to help solve the issue."
            )
            if msg:
                msg += "\n\n" + error_report_msg
            else:
                msg = error_report_msg

            self.add_button(_("_Send Error Report"), Gtk.ResponseType.OK)
            button = self.get_widget_for_response(Gtk.ResponseType.OK)
            style_context = button.get_style_context()
            style_context.add_class("suggested-action")

        msg = f"<span insert-hyphens='no'>{msg}</span>"
        self.format_secondary_markup(msg)
        self.set_default_response(Gtk.ResponseType.CLOSE)

    def do_response(self, response_id: int):
        if response_id == Gtk.ResponseType.OK:
            self.app.launch_whisperback(
                error_summary="PersistentStorage - %s" % self.title,
                error_report_msg=self.msg,
            )
        self.destroy()
