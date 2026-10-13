import json
import sqlite3
from pathlib import Path

class OperationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

class Store:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.workspace / 'course.sqlite3', timeout=30)
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
