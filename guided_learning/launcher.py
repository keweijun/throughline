"""The launcher setup adds, as the library's "Opening Throughline next time" card shows it (ADR 0017).

Add to desktop puts a copy of the launcher on the desktop; on macOS a symbolic link to the app instead, since a copy of
an app bundle would be a second Throughline for Launchpad and Spotlight to find. Show launcher reveals it in the file
manager, where the learner can pin it to the Dock or taskbar: pinning cannot be done reliably by a program.
"""
import shutil
import subprocess
from pathlib import Path

from . import commands
from .store import OperationError


def _popen(command):
    subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _output(command):
    try:
        found = subprocess.run(command, capture_output=True, text=True, timeout=15,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError):
        return ''
    return found.stdout.strip() if found.returncode == 0 else ''


class Launcher:
    """Where the launcher is on this computer, and the two things the library can do with it."""

    def __init__(self, path=None, platform=None, desktop=None, start=_popen, output=_output):
        self.platform = platform or commands.platform()
        self.path = Path(path) if path else commands.launcher_path()
        self._desktop = Path(desktop) if desktop else None
        self.start = start  # runs a program without waiting for it
        self.output = output  # runs a program and returns what it printed, or '' when it failed

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
        return {'platform': self.kind(), 'path': str(self.path), 'exists': self.path.exists()}

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
