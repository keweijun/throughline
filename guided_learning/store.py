import json
import sqlite3
from pathlib import Path

class OperationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

class Store:
    def __init__(self, workspace, create=False):
        """Open a course database; only `create` (course.init) may make a new one."""
        self.workspace = Path(workspace).resolve()
        database = self.workspace / 'course.sqlite3'
        if create:
            self.workspace.mkdir(parents=True, exist_ok=True)
        elif not database.is_file():
            raise OperationError('unknown_course', f'No course at {self.workspace}; run course.init first')
        self.db = sqlite3.connect(database, timeout=30)
        # Write-ahead logging lets readers run beside a writer, and commits append to one log instead of creating and
        # deleting a journal file each time. The mode is stored in the database; synchronous is set per connection.
        self.db.execute('PRAGMA synchronous=NORMAL')
        if self.db.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
            try:
                self.db.execute('PRAGMA journal_mode=WAL')
            except sqlite3.OperationalError:  # another connection is busy; a later operation switches
                pass
        if not create and not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='documents'").fetchone():
            self.db.close()
            raise OperationError('course_not_initialized', 'Run course.init first')
        if create:
            self.db.execute('CREATE TABLE IF NOT EXISTS documents (namespace TEXT, key TEXT, value TEXT NOT NULL, PRIMARY KEY(namespace, key))')
            self.db.commit()

    def get(self, namespace, key, default=None):
        row = self.db.execute('SELECT value FROM documents WHERE namespace=? AND key=?', (namespace, key)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, namespace, key, value):
        self.db.execute('INSERT INTO documents VALUES (?, ?, ?) ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value', (namespace, key, json.dumps(value, ensure_ascii=False)))
        return value

    def list(self, namespace):
        return [json.loads(row[0]) for row in self.db.execute('SELECT value FROM documents WHERE namespace=? ORDER BY key', (namespace,))]

    def delete(self, namespace, key):
        self.db.execute('DELETE FROM documents WHERE namespace=? AND key=?', (namespace, key))


def hold(workspace):
    """An idle connection for a long-running host. SQLite deletes the write-ahead log when the last connection closes,
    so without one every operation would create and delete the log and its index again, which is slow on Windows."""
    db = sqlite3.connect(Path(workspace) / 'course.sqlite3', timeout=30, check_same_thread=False)
    db.execute('SELECT 1 FROM documents LIMIT 1').fetchall()  # maps the log index, which keeps the log
    return db
