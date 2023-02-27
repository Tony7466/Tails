import os
import stat
from pathlib import Path
import shlex
import subprocess
import sys
from typing import List, Union, Optional

from tailslib import LIVE_USERNAME, LIVE_USER_UID, NOSYMFOLLOW_MOUNTPOINT
import tps.logging
from tps import _, TPS_MOUNT_POINT
from tps import executil
from tps.mountutil import mount, MOUNTFLAG_BIND
from tps.dbus.errors import TargetIsBusyError

logger = tps.logging.get_logger(__name__)


class FailedPrecondition(Exception):
    pass

class InvalidMountError(Exception):
    pass

class IsActiveException(Exception):
    pass

class IsInactiveException(Exception):
    pass


class Mount(object):
    """A mapping of a source file or directory to a target file or
    directory. When a feature is activated, all of its mounts are
    mounted, i.e. for each mount the source file or directory is mounted
    to the target file or directory.

    By default, the source is mounted via a bind mount. If uses_symlinks
    is true, instead of using a bind mount, symlinks are created from
    the source file or, if the source is a directory, each file in the
    source directory, to the target file or directory.

    This corresponds to the "link" option of live-boot(5). Below is the
    description of that option from the live-boot(5) man page (author:
    Daniel Baumann <mail@daniel-baumann.ch>, licensed under GPLv3):

    Create the directory structure of the source directory on the persistence media in DIR
    and create symbolic links from the corresponding place in DIR  to  each  file  in  the
    source  directory.   Existing files or directories with the same name as any link will
    be overwritten. Note that deleting the links in DIR will only remove the link, not the
    corresponding  file  in  the  source;  removed  links will reappear after a reboot. To
    permanently add or delete a file one must do so directly in the source directory.

    Effectively link will make only files already in the source directory persistent,  not
    any  other files in DIR. These files must be manually added to the source directory to
    make use of this option, and they will appear in DIR  in  addition  to  files  already
    there.  This  option  is useful when only certain files need to be persistent, not the
    whole directory they're in, e.g. some configuration files in a user's home directory."""

    def __init__(self, src: Union[str, Path], dest: Union[str, Path],
                 is_file=False, uses_symlinks=False,
                 tps_mount_point: str = TPS_MOUNT_POINT):

        self.tps_mount_point = Path(tps_mount_point)

        # If the source is not an absolute path, we make it an absolute
        # path below the Persistent Storage mount point.
        if not Path(src).is_absolute():
            self.src = Path(self.tps_mount_point, src).resolve()
        else:
            self.src = Path(src).resolve()  # type: Path
        self.dest = Path(dest).absolute()
        self.is_file = is_file
        self.uses_symlinks = uses_symlinks

        self.dest_orig = self.dest
        self.src_orig = self.src
        if os.getenv("NOSYMFOLLOW_MOUNTPOINT"):
            # We allow specifying the mount point for the nosymfollow
            # bind mount via an environment variable to allow tests to
            # specify a mount point in a temporary directory.
            self.nosymfollow_mountpoint = os.getenv("NOSYMFOLLOW_MOUNTPOINT")
        else:
            self.nosymfollow_mountpoint = NOSYMFOLLOW_MOUNTPOINT

        # To prevent symlink attacks, we don't allow a bind-mount's
        # source and target to be symlinks. To achieve that, we use the
        # bind-mount we created at NOSYMFOLLOW_MOUNTPOINT with the
        # nosymfollow option (see
        # config/chroot_local-includes/usr/local/lib/persistent-storage/pre-start)
        self.tps_mount_point = Path(self.nosymfollow_mountpoint +
                                    str(tps_mount_point))
        self.dest = Path(self.nosymfollow_mountpoint + str(self.dest))
        self.src = Path(self.nosymfollow_mountpoint + str(self.src))

        try:
            self._relative_src = \
                self.src.relative_to(self.tps_mount_point)
        except ValueError:
            raise InvalidMountError(f"Mount source {self.src} is outside of "
                                    f"the Persistent Storage mount point "
                                    f"{self.tps_mount_point}")

        # Check that the mount's source is below the Persistent Storage
        # mount point
        if self.tps_mount_point not in self.src.parents:
            raise InvalidMountError(f"Mount's source is outside of the "
                                    f"Persistent Storage mount point: {self}")

    def __str__(self):
        """The string representation of a mount."""
        return self.to_persistenceconf_line()

    def to_persistenceconf_line(self) -> str:
        """
        Representation of this mount as a persistence.conf line
        """
        options = ','.join(shlex.quote(option) for option in self.options)
        return shlex.quote(str(self.dest_orig)) + '\t' + options

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def __eq__(self, other: Union["Mount", str]):
        """Check if the mount is equal to another mount or the string
        representation of another mount"""

        # Ensure that the other object is a string
        other = str(other)

        # Remove leading and trailing whitespace
        other = other.strip()
        # Get the white-space separated elements of the other object
        elements = shlex.split(other, comments=True)

        if len(elements) != 2:
            # The other object has an invalid number of white-space
            # separated elements
            return False

        if elements[0] != str(self.dest_orig):
            # The destination doesn't match
            return False

        options = set(elements[1].split(','))
        if options != set(self.options):
            # The options don't match
            return False

        return True

    def __hash__(self):
        return hash(str(self))

    @property
    def options(self) -> List[str]:
        options = [f"source={str(self._relative_src)}"]
        if self.uses_symlinks:
            options.append("link")
        if self.is_file:
            options.append("file")
        return options

    def has_data(self) -> bool:
        if self.is_file:
            return self.src.exists()

        # Special handling for the Persistent directory:
        # Return False if the directory contains only an empty
        # "Tor Browser" directory.
        if self.src.name == "Persistent":
            if not self.src.exists():
                return False
            if not any(self.src.iterdir()):
                return False
            if any(d.name != "Tor Browser" for d in self.src.iterdir()):
                return True
            return Path(self.src, "Tor Browser").exists() and \
                any(Path(self.src, "Tor Browser").iterdir())

        return self.src.exists() and any(self.src.iterdir())

    def activate(self):
        try:
            self.check_is_inactive()
        except IsActiveException as e:
            # The mount is already active. It could be that two
            # different features have the same mount, which would
            # cause the mount to be activated again. To support that
            # case, we ignore the error here and just log a warning.
            logger.warning(str(e))
            return

        logger.info(f"Activating mount {self.dest}...")

        # Check if anything else is mounted on the destination
        src = _what_is_mounted_on(self.dest)
        if src:
            raise FailedPrecondition(f"Path {src} is mounted on {self.dest}")
        src = _what_is_mounted_on(self.dest_orig)
        if src:
            raise FailedPrecondition(f"Path {src} is mounted on {self.dest_orig}")

        # Return a meaningful error message when the destination path
        # contains a symlink (which is unsupported to prevent symlink
        # attacks). Note that this check is not for security - if a
        # symlink is created in the destination path after this check,
        # the mount will still fail, because we're using a nosymfollow
        # bind-mount.
        # To be able to test our protection against symlink attacks,
        # we only perform this check if we're not running a symlink
        # attack test (i.e. the SYMLINK_ATTACK_TEST env var is not set)
        if not os.getenv("SYMLINK_ATTACK_TEST"):
            for p in sorted(self.dest_orig.parents) + [self.dest_orig]:
                if p.is_symlink():
                    msg = f"Destination {self.dest_orig} contains a symlink: {p}"
                    raise FailedPrecondition(msg)

        # Create the mountpoint if it doesn't exist (we have to check
        # is_symlink() as well because exists() returns False for
        # broken symlinks)
        if not self.dest.is_symlink() and not self.dest.exists():
            if self.is_file:
                self.dest.touch(mode=0o600)
            else:
                self._create_dest_directory(self.dest)

        # Return a meaningful error message when the destination does
        # not have the expected file type. This check is not for
        # security (the file type could be changed after the check).
        # To be able to test our protection against symlink attacks,
        # we only perform this check if we're not running a symlink
        # attack test (i.e. the SYMLINK_ATTACK_TEST env var is not set)
        if not os.getenv("SYMLINK_ATTACK_TEST"):
            if self.is_file and not self.dest.is_file():
                msg = f"Destination {self.dest_orig} exists but is not a regular file"
                raise FailedPrecondition(msg)
            if not self.is_file and not self.dest.is_dir():
                msg = f"Destination {self.dest_orig} exists but is not a directory"
                raise FailedPrecondition(msg)

        if self.uses_symlinks:
            self._activate_using_symlinks()
        else:
            self._activate_using_bind_mount()

        logger.info(f"Done activating mount {self.dest}")

    def _activate_using_symlinks(self):
        if self.is_file:
            # Create the source file if it doesn't exist
            if not self.src.exists():
                self.src.touch(mode=0o700)
            # Create the symlink
            self._create_symlink(self.src, self.dest)
            return

        # Create the source directory if it doesn't exist
        if not self.src.exists():
            self.src.mkdir(mode=0o700, parents=True)
            # Set the same ownership and permissions of the destination
            # directory on the source directory
            _chown_ref(self.dest, self.src)
            _chmod_ref(self.dest, self.src)
            # The directory is empty, so there are no symlinks to create
            return

        # Create symlinks for all files in the directory
        for dir, subdirs, files in os.walk(self.src):
            dest_dir = os.path.join(self.dest, os.path.relpath(dir, self.src))
            for f in subdirs + files:
                src = Path(dir, f)
                dest = Path(dest_dir, f)
                self._create_symlink(src, dest)

    @staticmethod
    def _create_symlink(src: Path, dest: Path):
        if src.is_dir():
            # Create the destination directory if it doesn't exist
            dest.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Make the destination have the same owner and permissions
            # as the source directory.
            _chown_ref(src, dest)
            _chmod_ref(src, dest)
        else:
            # Delete the destination file if it already exists (we have
            # to check is_symlink() as well because exists() returns
            # False for broken symlinks)
            if dest.is_symlink() or dest.exists():
                logger.info(f"Deleting file {dest} because it's in the way")
                dest.unlink()
            dest.symlink_to(src)
            # Make the symlink have the same owner as the source directory.
            _chown_ref(src, dest)

    def _activate_using_bind_mount(self):
        # If the source doesn't exist on the Persistent Storage, we
        # bootstrap it with the content of the destination, as it's done
        # by live-boot's activate_custom_mounts() function.
        if not self.src.exists():
            # Create the parent directory
            self.src.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            executil.check_call(["cp", "-a", self.dest, self.src])
            executil.check_call(["sync", "--file-system", self.src])

        # Bind-mount the source to the destination. To prevent symlink
        # attacks, we use mount(2) of the libc instead of the mount(8)
        # command, because the latter calls readlink(2) on the target
        # path, which makes it resolve symlinks even though the
        # nosymfollow option is set on the target filesystem.
        mount(self.src, self.dest, MOUNTFLAG_BIND)

    def deactivate(self):
        try:
            self.check_is_active()
        except IsInactiveException as e:
            # The mount is not active. It could be that two different
            # features have the same mount, which would cause the mount
            # to be deactivated again. To support that case, we ignore
            # the error here and just log a warning.
            logger.warning(str(e))
            return

        if self.uses_symlinks:
            self._deactivate_using_symlinks()
        else:
            self._deactivate_using_bind_mount()

    def _deactivate_using_symlinks(self):
        # Remove symlinks
        for dir, subdirs, files in os.walk(self.src):
            dest_dir = os.path.join(self.dest, os.path.relpath(dir, self.src))
            for f in files:
                dest = Path(dest_dir, f)
                if not dest.is_symlink():
                    continue
                dest.unlink()
        # Delete the source directory if it's empty, otherwise it
        # would be impossible to successfully disable the Dotfiles
        # feature when the Dotfiles directory is empty: this operation
        # would fail because tps will still think the feature is
        # active (technically it is: 0% of "no setup needed" == 100%
        # of "no setup needed").
        if not any(self.src.iterdir()):
            self.src.rmdir()

    def _deactivate_using_bind_mount(self):
        # Unmount the destination directory
        try:
            executil.run(["umount", self.dest], check=True, text=True,
                         stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            # Print the subprocess stderr
            print(e.stderr, file=sys.stderr)
            if e.returncode == 32 and "target is busy" in e.stderr:
                # Translators: Don't translate {target}, it's a placeholder
                msg = _(
                    "Can't unmount target {target}, some process is still"
                    " using it. Please close all applications that could"
                    " be accessing the target and try again."
                ).format(target=self.dest_orig)
                raise TargetIsBusyError(msg) from e
            raise

    def is_active(self) -> bool:
        try:
            self.check_is_active()
            return True
        except IsInactiveException:
            return False

    def check_is_active(self):
        """Check if the mount is active. Raise an IsInactiveException
        if the feature is inactive."""
        if self.uses_symlinks:
            self._check_is_active_using_symlinks()
        else:
            self._check_is_active_using_bind_mount()

    def check_is_inactive(self):
        """Check if the mount is inactive. Raise an IsActiveException
        if the feature is active."""
        if self.is_active():
            raise IsActiveException(f"Mount {self.dest} is active")

    def _check_is_active_using_symlinks(self):
        if not self.src.exists():
            # If the source doesn't exist, the feature can't be active.
            raise IsInactiveException(f"Mount {self.dest} is inactive: Symlink source {self.src} does not exist")

        if not self.dest.is_symlink() and not self.dest.exists():
            # If the destination doesn't exist, the feature can't be active.
            raise IsInactiveException(f"Mount {self.dest} is inactive: Destination {self.dest} does not exist")

        for dir, _, files in os.walk(self.src):
            dest_dir = os.path.join(self.dest, os.path.relpath(dir, self.src))
            for f in files:
                src = Path(dir, f)
                dest = Path(dest_dir, f)
                if not dest.is_symlink():
                    raise IsInactiveException(f"Mount {self.dest} is inactive: Symlink {dest} does not exist")
                if dest.readlink() != src:
                    raise IsInactiveException(
                        f"Mount {self.dest} is inactive: Symlink {dest} does not resolve to the symlink source {src} but to {dest.resolve()}")

    def _check_is_active_using_bind_mount(self):
        # Check if the Persistent Storage cleartext device is already
        # mounted on the destination
        if not _is_mountpoint(self.dest):
            raise IsInactiveException(f"Mount {self.dest} is inactive: {self.dest} it not a mountpoint")

    def _create_dest_directory(self, path: Path):
        """Create the destination directory of a mount in the same way as
        it's done in live-boot's activate_custom_mounts() function, i.e.
        by deleting existing files that are in the way and by setting the
        owner to the UID of amnesia (live-boot sets it to 1000) on
        directories below /home/amnesia"""
        logger.debug(f"Creating mount destination {path}")
        for p in sorted(path.parents) + [path]:
            if p.is_file():
                # Delete existing files that are in the way
                p.unlink()
            p.mkdir(mode=0o700, parents=True, exist_ok=True)
            if Path(f"{self.nosymfollow_mountpoint}/home/{LIVE_USERNAME}") in \
                    p.parents:
                logger.debug(f"Changing owner of mount destination {path} to "
                             f"UID {LIVE_USER_UID}")
                # If dest is in /home/amnesia, set ownership to the amnesia
                # user.
                os.chown(p, LIVE_USER_UID, LIVE_USER_UID)


def _what_is_mounted_on(path: Union[str, Path]) -> Optional[str]:
    try:
        output = executil.check_output(
            ["findmnt", "--output=SOURCE", "--noheadings", "--notruncate",
             "--canonicalize", f"--mountpoint={path}"],
        )
    except subprocess.CalledProcessError:
        # We assume that any non-zero exit code means that no mount was
        # found for the specified mountpoint.
        return None
    return output.strip()


def _is_mountpoint(path: Union[str, Path]) -> bool:
    try:
        executil.check_call(["mountpoint", "--quiet", "--nofollow", path])
    except subprocess.CalledProcessError:
        return False
    return True


def _chown_ref(source: Union[str, Path], dest: Union[str, Path]):
    """Change the owner and group of dest to the ones of source"""
    # If the destination is a symlink, we want to change the symlinks
    # owner, so we set --no-dereference.
    # We don't use the --reference option here but retrieve the UID and
    # GID ourselves because chown resolves symlinks of the reference file.
    uid = source.lstat().st_uid
    gid = source.lstat().st_gid
    executil.check_call(["chown", "--no-dereference", f"{uid}:{gid}", dest])


def _chmod_ref(source: Union[str, Path], dest: Union[str, Path]):
    """Change the permissions of dest to the ones of source"""
    # Don't call chmod when the destination is a symlink, because we
    # don't want to change the permissions of the symlink's target and
    # it's not possible to change the permission of a symlink itself.
    if Path(dest).is_symlink():
        return
    # We don't use the --reference option here but retrieve the UID and
    # GID ourselves because chmod resolves symlinks of the reference file.
    chmod_mode = stat.S_IMODE(source.lstat().st_mode)
    executil.check_call(["chmod", "%o" % chmod_mode, source, dest])
