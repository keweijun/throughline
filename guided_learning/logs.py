"""Where the host's log goes: `<library>/.throughline/host.log`, rotated so it never grows without end.

The host writes its own log; what the process prints before logging starts (a crash on import, say) goes to
`host-output.log`, which each launch starts afresh. `doctor` names both."""
import collections
import logging
import logging.handlers
import threading

from . import library

LOG, OUTPUT = 'host.log', 'host-output.log'
MAX_BYTES, BACKUPS = 2 * 1024 * 1024, 3
FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'


def log_path():
    return library.state_dir() / LOG


def output_path():
    return library.state_dir() / OUTPUT


def configure(path=None):
    """Send this process's log records (warnings, errors and the host's own notes) to the rotating host log."""
    path = path or log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding='utf-8',
                                                   delay=True)
    handler.setFormatter(logging.Formatter(FORMAT))
    root = logging.getLogger()
    for old in [h for h in root.handlers if getattr(h, 'throughline', False)]:
        root.removeHandler(old)
        old.close()
    handler.throughline = True
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return handler


class Tail:
    """The last lines a child process (Codex) wrote to stderr, read on a thread of their own so the pipe never fills.

    Codex says why it failed there (no login, a bad config file) when its JSON replies say nothing."""

    def __init__(self, stream, lines=40):
        self.lines = collections.deque(maxlen=lines)
        self.thread = threading.Thread(target=self._read, args=(stream,), name='codex-stderr', daemon=True)
        self.thread.start()

    def _read(self, stream):
        try:
            for line in stream:
                if line.strip():
                    self.lines.append(line.rstrip())
        except (OSError, ValueError):
            pass

    def text(self, wait=0.5):
        self.thread.join(wait)
        return '\n'.join(self.lines)

    def log(self, logger, what):
        """Record the tail with what went wrong, if Codex wrote anything."""
        text = self.text()
        if text:
            logger.warning('%s; Codex wrote:\n%s', what, text)
