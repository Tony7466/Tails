import logging
from gi.repository import GLib, Gtk, GObject

from tails_server import _
from tails_server import dbus_interface
from tails_server import tor_util
from tails_server.exceptions import InvalidStatusError
from tails_server.config import TOR_BOOTSTRAPPED_TARGET
from tails_server.config import STATUS_UI_FILE


# This would be prettier as an Enum, but Widget.emit only allows strings as args
class Status(object):
    installing = "0"
    installed = "1"
    uninstalling = "2"
    uninstalled = "3"

    starting = "10"
    running = "11"
    stopping = "12"
    stopped = "13"

    publishing = "20"
    online = "21"
    offline = "22"

    tor_is_not_running = "30"
    tor_is_running = "31"

    error = "40"
    invalid = "41"


status_to_string = {
    Status.starting: _("Starting"),
    Status.running: _("Running"),
    Status.stopping: _("Stopping"),
    Status.stopped: _("Stopped"),

    Status.publishing: _("Registering onion address"),
    Status.online: _("Online"),
    Status.offline: _("Offline"),

    Status.installing: _("Installing"),
    Status.installed: _("Installed"),
    Status.uninstalling: _("Uninstalling"),
    Status.uninstalled: _("Not installed"),

    Status.tor_is_not_running: _("Tor is not running"),
    Status.tor_is_running: _("Tor is running"),
    Status.error: _("An error occurred. See the log for details."),
    Status.invalid: _("The service is in an invalid state. See the log for details."),
}


class ServiceStatus(Gtk.Widget):

    @classmethod
    def register_signal(cls):
        GObject.signal_new(
            "update",       # signal name
            ServiceStatus,  # object type
            GObject.SIGNAL_RUN_FIRST | GObject.SIGNAL_ACTION,  # flags
            None,           # return type
            (str,),         # argument types
        )

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.connect("update", self.on_update)
        self.dbus_monitor = dbus_interface.StatusMonitor(self.service.systemd_service,
                                                         self.dbus_receiver)
        self.tor_dbus_monitor = dbus_interface.StatusMonitor(TOR_BOOTSTRAPPED_TARGET,
                                                             self.tor_dbus_receiver)
        self.service_status = str()
        self.onion_status = str()
        self.tor_status = str()
        self.installation_status = str()
        self.status = str()

    def on_update(self, obj, status):
        logging.debug("New status for service %r: %r", self.service.name, status)
        GLib.idle_add(self.update, status)

    def update(self, status):
        self.update_substates(status)

        if status in [Status.error, Status.invalid]:
            new_status = status
        else:
            new_status = self.get_status_from_substates()
        if new_status == self.status:
            return
        self.status = new_status
        self.update_config_panel()
        self.update_service_list()

    def get_status_from_substates(self):
        if self.tor_status != Status.tor_is_running:
            logging.debug("Setting status to tor status %r", self.tor_status)
            return self.tor_status
        elif self.installation_status != Status.installed:
            logging.debug("Setting status to installation status %r", self.installation_status)
            return self.installation_status
        elif self.service_status != Status.running:
            logging.debug("Setting status to service status %r", self.service_status)
            return self.service_status
        else:
            logging.debug("Setting status to onion status %r", self.onion_status)
            return self.onion_status

    def update_substates(self, status):
        if status in [Status.tor_is_running,
                      Status.tor_is_not_running]:
            logging.debug("Setting tor status to %r", status)
            self.tor_status = status
        elif status in [Status.online,
                        Status.offline,
                        Status.publishing]:
            logging.debug("Setting onion status to %r", status)
            self.onion_status = status
        elif status in [Status.starting,
                        Status.running,
                        Status.stopping,
                        Status.stopped]:
            logging.debug("Setting service status to %r", status)
            self.service_status = status
        elif status in [Status.installing,
                        Status.installed,
                        Status.uninstalling,
                        Status.uninstalled]:
            logging.debug("Setting installation status to %r", status)
            self.installation_status = status

    def update_config_panel(self):
        builder = self.service.config_panel.builder
        box = builder.get_object("box_status")
        label = builder.get_object("label_status_value")
        visual_widget = self.get_visual_widget(self.status)

        for child in box.get_children():
            box.remove(child)

        label.set_label(status_to_string[self.status])

        box.pack_start(visual_widget, expand=False, fill=False, padding=0)
        box.pack_start(label, expand=False, fill=False, padding=0)
        # XXX: Find out why the status only refreshes after config_panel.show() and do something
        # more lightweight
        if self.service.config_panel.is_active:
            self.service.config_panel.show()

    def update_service_list(self):
        try:
            service_row = self.service.gui.service_list.service_row_dict[self.service]
        except KeyError:
            return
        builder = service_row.builder
        box = builder.get_object("box_status_inner")
        label = builder.get_object("label_status_value")

        for child in box.get_children():
            box.remove(child)

        visual_widget = self.get_visual_widget(self.status)
        label_value = None
        if self.status in (Status.offline, Status.stopped):
            label_value = _("Off")
        if self.status in (Status.online,):
            label_value = _("On")

        if visual_widget:
            box.pack_start(visual_widget, expand=False, fill=False, padding=0)
        if label_value:
            label.set_label(label_value)
            box.pack_start(label, expand=False, fill=False, padding=0)

    def get_visual_widget(self, status):
        new_builder = Gtk.Builder()
        new_builder.add_from_file(STATUS_UI_FILE)
        if status in (Status.starting, Status.stopping, Status.installing,
                      Status.uninstalling, Status.publishing):
            return new_builder.get_object("spinner")
        if status in (Status.offline, Status.stopped):
            return new_builder.get_object("image_off")
        if status == Status.online:
            return new_builder.get_object("image_on")
        if status in (Status.error, Status.tor_is_not_running):
            return new_builder.get_object("image_error")
        raise InvalidStatusError("No visual widget for status %r defined" % status)

    def dbus_receiver(self, status):
        """Receives systemd status value from dbus and sets the status accordingly.
        valid status values: "active", "activating", "inactive", "deactivating"""

        if status == "activating":
            self.emit("update", Status.starting)
        if status == "active":
            self.emit("update", Status.running)
        if status == "deactivating":
            self.emit("update", Status.stopping)
        if status == "inactive":
            self.emit("update", Status.stopped)

    def tor_dbus_receiver(self, status):
        if status == "inactive":
            self.emit("update", Status.tor_is_not_running)
        if status == "active":
            self.emit("update", Status.tor_is_running)

    def guess_status(self):
        self.installation_status = Status.installed if self.service.is_installed \
            else Status.uninstalled

        self.service_status = Status.running if self.service.is_running \
            else Status.stopped

        self.tor_status = Status.tor_is_running if tor_util.tor_has_bootstrapped() \
            else Status.tor_is_not_running

        if self.service.address and self.service.is_published:
            self.onion_status = Status.online
        else:
            self.onion_status = Status.offline

        self.emit("update", self.get_status_from_substates())

    def make_states_consistent(self):
        if self.service_status == Status.running and self.onion_status == Status.offline:
            self.service.run_threaded(self.service.add_onion)
