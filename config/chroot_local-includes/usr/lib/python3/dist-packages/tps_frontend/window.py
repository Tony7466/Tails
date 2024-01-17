import subprocess
from logging import getLogger

# Only required for type hints
from typing import TYPE_CHECKING, Optional

import gi
from gi.repository import Gio, GLib, GObject, Gtk
from tps import IN_PROGRESS_STATES, InvalidBootDeviceErrorType, State
from tps.dbus.errors import DBusError, NotEnoughMemoryError, TargetIsBusyError

from tps_frontend import WINDOW_UI_FILE, _
from tps_frontend.change_passphrase_dialog import ChangePassphraseDialog
from tps_frontend.views.creation_view import CreationView
from tps_frontend.views.deleted_view import DeletedView
from tps_frontend.views.fail_view import FailView
from tps_frontend.views.features_view import FeaturesView
from tps_frontend.views.locked_view import LockedView
from tps_frontend.views.passphrase_view import PassphraseView
from tps_frontend.views.spinner_view import SpinnerView
from tps_frontend.views.welcome_view import WelcomeView

if TYPE_CHECKING:
    from gi.repository import Gdk

    from tps_frontend.application import Application

gi.require_version("Handy", "1")
from gi.repository import Handy  # noqa: E402

Handy.init()

logger = getLogger(__name__)



@Gtk.Template.from_file(WINDOW_UI_FILE)
class Window(Gtk.ApplicationWindow):
    __gtype_name__ = "Window"

    view_box = Gtk.Template.Child()  # type: Gtk.Box
    change_passphrase_button = Gtk.Template.Child()  # type: Gtk.Button
    restart_button = Gtk.Template.Child()  # type: Gtk.Button
    delete_button = Gtk.Template.Child()  # type: Gtk.Button

    def __init__(self, app: "Application", bus: Gio.DBusConnection):
        """Initialize the main window"""
        super().__init__(application=app, title=_("Persistent Storage"))
        self.app = app
        self.service_proxy = self.app.service_proxy
        self.active_view = None
        self.was_deleting = False

        # Initialize the fail view (we do this early because it's being
        # used by self.display_error())
        self.fail_view = FailView(self)

        # Initialize the remaining views
        self.creation_view = CreationView(self)
        self.deleted_view = DeletedView(self)
        self.spinner_view = SpinnerView(self)
        self.features_view = FeaturesView(self, bus)
        self.passphrase_view = PassphraseView(self)
        self.locked_view = LockedView(self)
        self.welcome_view = WelcomeView(self)

        # Subscribe to changes of the service name owner, so that we
        # notice when the service exits unexpectedly.
        self.service_proxy.connect("notify::g-name-owner", self.on_name_owner_changed)

        # Subscribe to changes of the service's properties, so that we
        # can react to the Persistent Storage being created or deleted.
        self.service_proxy.connect("g-properties-changed", self.on_properties_changed)

        self.name_owner = self.service_proxy.get_name_owner()

        variant = self.service_proxy.get_cached_property("State")
        if not variant:
            self.state = State.UNKNOWN
        else:
            self.state = State[variant.get_string()]

        self.refresh_view()

    def refresh_view(self):
        # Choose which view to show
        if not self.name_owner:
            self.fail_view.show()
        elif self.state == State.NOT_CREATED and self.was_deleting:
            self.deleted_view.show()
        elif self.state == State.NOT_CREATED:
            self.welcome_view.show()
        elif self.state == State.NOT_UNLOCKED:
            self.locked_view.show()
        elif self.state == State.CREATING:
            self.creation_view.show()
        elif self.state in (State.DELETING, State.UNLOCKING):
            self.spinner_view.show()
        elif self.state == State.UNLOCKED:
            self.features_view.show()
        else:
            self.fail_view.show()

    def on_name_owner_changed(self, proxy: Gio.DBusProxy, pspec: GObject.ParamSpec):
        self.name_owner = proxy.get_name_owner()
        if self.name_owner:
            logger.info("Persistent Storage D-Bus service appeared")
        else:
            logger.warning("Persistent Storage D-Bus service vanished")
            # The service is unavailable, so we don't know its state
            self.state = State.UNKNOWN
        self.refresh_view()

    def on_properties_changed(
        self,
        proxy: Gio.DBusProxy,
        changed_properties: GLib.Variant,
        invalidated_properties: list[str],
    ):
        if not any(p for p in changed_properties if p == "State"):
            return

        variant = changed_properties.lookup_value("State")
        self.state = State[variant.get_string()]

        # We remember if the state was DELETING, so that we know if we
        # should display the welcome view or the deleted view when the
        # state changes to NOT_CREATED
        if self.state == State.DELETING:
            self.was_deleting = True
        elif self.state != State.NOT_CREATED:
            self.was_deleting = False

        # The Persistent Storage state changed, so we switch to
        # another view if needed
        self.refresh_view()

    @Gtk.Template.Callback()
    def on_delete_button_clicked(self, button: Gtk.Button):
        can_delete = True
        if self.active_view != self.locked_view:
            can_delete = False
            explanation = _(
                "To delete the Persistent Storage, restart Tails without "
                "unlocking the Persistent Storage and open "
                "the Persistent Storage settings again.",
            )
        elif not self.service_proxy.get_cached_property("CanDelete"):
            can_delete = False
            error: GLib.Variant = self.service_proxy.get_cached_property("Error")
            if (
                error
                and InvalidBootDeviceErrorType(error.get_uint32())
                == InvalidBootDeviceErrorType.READ_ONLY
            ):
                explanation = _(
                    "Impossible to delete the Persistent Storage because "
                    "the USB stick is read-only.\n\n"
                    "To delete the Persistent Storage, turn off the read-only "
                    "protection of the USB stick, restart Tails without unlocking "
                    "the Persistent Storage "
                    "and open the Persistent Storage settings again.",
                )
            else:
                explanation = _("Impossible to delete the Persistent Storage")

        if can_delete:
            dialog = Gtk.MessageDialog(
                self,
                Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.WARNING,
                Gtk.ButtonsType.NONE,
                _("Delete Persistent Storage"),
            )
            dialog.format_secondary_text(
                _(
                    "Are you sure that you want to delete your Persistent Storage? "
                    "This action cannot be undone.",
                ),
            )
            dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
            dialog.add_button(_("_Delete Persistent Storage"), Gtk.ResponseType.OK)
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            button = dialog.get_widget_for_response(Gtk.ResponseType.OK)
            style_context = button.get_style_context()
            style_context.add_class("destructive-action")
            result = dialog.run()
            dialog.destroy()
            if result == Gtk.ResponseType.OK:
                self.spinner_view.show()
                self.spinner_view.status_label.set_label(
                    _("Deleting your Persistent Storage..."),
                )
                self.service_proxy.call(
                    method_name="Delete",
                    parameters=None,
                    flags=Gio.DBusCallFlags.NONE,
                    timeout_msec=GLib.MAXINT,
                    cancellable=None,
                    callback=self.on_delete_call_finished,
                )
        else:
            dialog = Gtk.MessageDialog(
                self,
                Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.INFO,
                Gtk.ButtonsType.NONE,
                _("Delete Persistent Storage"),
            )
            dialog.format_secondary_text(explanation)
            dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
            dialog.set_default_response(Gtk.ResponseType.OK)
            dialog.run()
            dialog.destroy()

    @Gtk.Template.Callback()
    def on_close(self, window: Gtk.Window, event: "Gdk.Event"):
        if self.state in IN_PROGRESS_STATES:
            msg = _(
                "Sorry, you can't close this app until the "
                "ongoing operation has completed.",
            )
            self.display_error(_("Please wait"), msg, False)
            return True
        return False

    @Gtk.Template.Callback()
    def on_change_passphrase_button_clicked(self, button: Gtk.Button):
        dialog = ChangePassphraseDialog(self, self.service_proxy)
        dialog.run()

    @Gtk.Template.Callback()
    def on_restart_button_clicked(self, button: Gtk.Button):
        subprocess.run(["sudo", "-n", "/sbin/reboot"])

    def on_create_call_finished(self, proxy: GObject.Object, res: Gio.AsyncResult):
        try:
            proxy.call_finish(res)
        except GLib.Error as e:
            logger.error(f"failed to create Persistent Storage: {e.message}")

            if NotEnoughMemoryError.is_instance(e):
                # The system doesn't have enough memory to create the
                # Persistent Storage. This is an expected error which
                # we don't want error reports for.
                NotEnoughMemoryError.strip_remote_error(e)
                self.display_error(
                    _("Not enough memory to create Persistent Storage"),
                    e.message,
                    with_send_report_button=False,
                )
            else:
                DBusError.strip_remote_error(e)
                self.display_error(_("Failed to create Persistent Storage"), e.message)

            if self.active_view == self.creation_view:
                self.close()
            return

    def on_delete_call_finished(self, proxy: GObject.Object, res: Gio.AsyncResult):
        try:
            proxy.call_finish(res)
        except GLib.Error as e:
            logger.error(f"failed to delete Persistent Storage: {e.message}")

            if TargetIsBusyError.is_instance(e):
                # Some process is still accessing the target. This is
                # an expected error which we don't want error reports
                # for.
                TargetIsBusyError.strip_remote_error(e)
                self.display_error(
                    _("Error deleting Persistent Storage"),
                    e.message,
                    with_send_report_button=False,
                )
            else:
                DBusError.strip_remote_error(e)
                self.display_error(_("Error deleting Persistent Storage"), e.message)
        self.refresh_view()

    def display_error(self, title: str, msg: str, with_send_report_button: Optional[bool] = None):
        if with_send_report_button is None:
            # Don't show the send report button if the failure view is the
            # active view, because we already show a send report button
            # there.
            with_send_report_button = self.active_view != self.fail_view
        self.app.display_error(title, msg, with_send_report_button)
