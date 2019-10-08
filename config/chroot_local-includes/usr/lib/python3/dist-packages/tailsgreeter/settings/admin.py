import os
import os.path
import logging
import pipes
import subprocess

import tailsgreeter.config
from tailsgreeter.settings.utils import read_settings, write_settings


class AdminSetting(object):
    """Setting controlling the sudo password"""

    def __init__(self):
        self.password = None
        self.settings_file = tailsgreeter.config.admin_password_path

    def apply_to_upcoming_session(self):
        if self.password:
            proc = subprocess.run(
                ["mkpasswd", "-s", "--method=sha512crypt"],
                input=pipes.quote(self.password).encode(),
                capture_output=True,
                check=True,
            )
            hashed_and_salted_pw = proc.stdout.decode().strip()

            write_settings(self.settings_file, {
                'TAILS_USER_PASSWORD': pipes.quote(hashed_and_salted_pw),
            })
            logging.debug('password written to %s', self.settings_file)
            return

        # Try to remove the password file
        try:
            os.unlink(self.settings_file)
            logging.debug('removed %s', self.settings_file)
        except OSError:
            # It's bad if the file exists and couldn't be removed, so we
            # we raise the exception in that case (which prevents the login)
            if os.path.exists(self.settings_file):
                raise

    def load(self) -> bool:
        try:
            settings = read_settings(self.settings_file)
        except FileNotFoundError:
            logging.debug("No persistent admin settings file found (path: %s)", self.settings_file)
            return False

        password = settings.get('TAILS_USER_PASSWORD')
        if password:
            self.password = password
            logging.debug("Loaded admin password setting")
            return True
