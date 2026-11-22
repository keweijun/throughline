"""The launcher setup adds, as the library's "Opening Throughline next time" card shows it (ADR 0017).

Add to desktop puts a copy of the launcher on the desktop; on macOS a symbolic link to the app instead, since a copy of
an app bundle would be a second Throughline for Launchpad and Spotlight to find. Add to Dock keeps it in macOS's Dock,
or in GNOME's dock (its favourite apps). Windows lets no program pin itself to the taskbar or Start, so there the card
says how; Show launcher, which reveals it in the file manager, stays for older pages.
"""
import ast
import shutil
import subprocess
from pathlib import Path

from . import commands
from .store import OperationError


def _popen(command):
    subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _output(command):
    """What `command` printed, or None when it could not run or failed."""
    try:
        found = subprocess.run(command, capture_output=True, text=True, timeout=15,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return found.stdout.strip() if found.returncode == 0 else None


class Launcher:
    """Where the launcher is on this computer, and the two things the library can do with it."""

    def __init__(self, path=None, platform=None, desktop=None, start=_popen, output=_output):
        self.platform = platform or commands.platform()
        self.path = Path(path) if path else commands.launcher_path()
        self._desktop = Path(desktop) if desktop else None
        self.start = start  # runs a program without waiting for it
        self.output = output  # runs a program and returns what it printed, or None when it failed

    def kind(self):
        """The platform, with macOS split by which Applications folder holds the launcher (its words differ)."""
        if self.platform == 'darwin' and self.path.parent != commands.APPLICATIONS:
            return 'darwin-home'
        return self.platform

    def desktop(self):
        if self._desktop:
            return self._desktop
        if self.platform == 'nt':  # the Desktop may be redirected, to OneDrive for one
            found = self.output(['powershell', '-NoProfile', '-NonInteractive', '-Command', "[Environment]::GetFolderPath('Desktop')"])
        elif self.platform == 'linux':
            found = self.output(['xdg-user-dir', 'DESKTOP']) if shutil.which('xdg-user-dir') else ''
        else:
            found = ''
        return Path(found) if found else Path.home() / 'Desktop'

    def status(self):
        exists = self.path.exists()
        dock = exists and self.can_dock()
        return {'platform': self.kind(), 'path': str(self.path), 'exists': exists, 'dock': dock,
                'docked': dock and self.docked()}

    # The Dock: macOS's, or GNOME's favourite apps, which its dock shows. Elsewhere there is none Throughline can add to.

    def _favourites(self):
        found = self.output(['gsettings', 'get', 'org.gnome.shell', 'favorite-apps'])
        if found is None:
            return None
        try:
            apps = ast.literal_eval(found.removeprefix('@as ').strip())
        except (ValueError, SyntaxError):
            return None
        return [str(app) for app in apps] if isinstance(apps, list) else None

    def can_dock(self):
        if self.platform == 'darwin':
            return True
        if self.platform == 'linux' and shutil.which('gsettings'):
            return self.output(['gsettings', 'writable', 'org.gnome.shell', 'favorite-apps']) == 'true'
        return False

    def docked(self):
        if self.platform == 'darwin':
            found = self.output(['defaults', 'read', 'com.apple.dock', 'persistent-apps'])
            return found is not None and self.path.as_uri() in found
        return self.path.name in (self._favourites() or [])

    def add_to_dock(self):
        self._require()
        if not self.can_dock():
            raise OperationError('cannot_dock', 'Throughline cannot add itself to the dock here; pin it from the app menu.')
        if self.docked():
            return {'docked': True}
        if self.platform == 'darwin':
            tile = ('<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key>'
                    f'<string>{self.path.as_uri()}/</string><key>_CFURLStringType</key><integer>15</integer>'
                    '</dict></dict></dict>')
            if self.output(['defaults', 'write', 'com.apple.dock', 'persistent-apps', '-array-add', tile]) is None:
                raise OperationError('cannot_dock', 'The Dock could not be changed.')
            self.start(['killall', 'Dock'])  # the Dock reads its apps again when it restarts
        else:
            apps = self._favourites()
            if apps is None:
                raise OperationError('cannot_dock', 'The dock could not be read.')
            value = '[' + ', '.join(repr(app) for app in [*apps, self.path.name]) + ']'
            if self.output(['gsettings', 'set', 'org.gnome.shell', 'favorite-apps', value]) is None:
                raise OperationError('cannot_dock', 'The dock could not be changed.')
        return {'docked': True}

    def _require(self):
        if not self.path.exists():
            raise OperationError('launcher_missing', 'Throughline has no launcher on this computer yet. Run `guided-learning setup` to add one.')

    def add_to_desktop(self):
        self._require()
        folder = self.desktop()
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / self.path.name
        if self.platform == 'darwin':
            if target.is_symlink():
                target.unlink()
            elif target.exists():
                raise OperationError('desktop_taken', f'{target} is already on your desktop.')
            target.symlink_to(self.path, target_is_directory=True)
            return {'path': str(target)}
        shutil.copyfile(self.path, target)
        if self.platform == 'linux':
            target.chmod(0o755)
            if shutil.which('gio'):  # GNOME launches a desktop file only once it is marked trusted
                self.output(['gio', 'set', str(target), 'metadata::trusted', 'true'])
        return {'path': str(target)}

    def show(self):
        self._require()
        if self.platform == 'nt':
            command = ['explorer', f'/select,{self.path}']
        elif self.platform == 'darwin':
            command = ['open', '-R', str(self.path)]
        else:
            command = ['xdg-open', str(self.path.parent)]  # no portable way to select the file itself
        try:
            self.start(command)
        except OSError as exc:
            raise OperationError('cannot_show', f'Could not open {self.path.parent} ({exc}).') from exc
        return {'shown': str(self.path)}
