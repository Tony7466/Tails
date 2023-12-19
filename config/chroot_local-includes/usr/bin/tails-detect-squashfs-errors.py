#!/usr/bin/env python3

"""
  Detect SQUASHFS error and if detected reate /run/squashfs_failed.
  That file will be used to show the user an error.

  Copyright (C) 2023 Tails developers <tails@boum.org>

  You can redistribute  it and/or modify it under the  terms of the GNU
  General Public License as published by the Free Software Foundation;
  either version 3 of the License, or (at your option) any later version.

  This program  is distributed in the  hope that it will  be useful, but
  WITHOUT   ANY  WARRANTY;   without  even   the  implied   warranty  of
  MERCHANTABILITY  or FITNESS  FOR A  PARTICULAR PURPOSE.   See  the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import pathlib
import systemd.journal


j = systemd.journal.Reader()
j.this_boot()
j.this_machine()
j.log_level(systemd.journal.LOG_ERR)
j.add_match(SYSLOG_IDENTIFIER="kernel")

j.seek_tail()
j.get_previous()

squashfs_failed = pathlib.Path("/run/squashfs_failed")
squashfs_failed.unlink(missing_ok=True)

while True:
    state_change = j.wait(-1)
    if state_change == systemd.journal.APPEND:
        for e in j:
            if e["MESSAGE"].startswith("SQUASHFS error:"):
                print(e["MESSAGE"])
                squashfs_failed.touch(exist_ok=True)
