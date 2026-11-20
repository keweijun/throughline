"""A learning host as 0.52–0.54.0 answered: /api/health without a key, the rest only with the key it was given (an
empty one takes none), no /api/sign-in, and /api/shutdown stops it. Prints its port, then serves until stopped."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = sys.argv[1] if len(sys.argv) > 1 else ''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def answer(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_request(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        if self.path == '/api/health':
            return self.answer(200, {'pid': os.getpid(), 'launch_id': None})
        if not KEY or self.headers.get('X-Throughline-Key') != KEY:
            return self.answer(401, {'error': 'This browser is not signed in to Throughline.', 'code': 'not_signed_in'})
        if self.command == 'POST' and self.path == '/api/shutdown':
            self.answer(200, {'stopping': True})
            threading.Thread(target=server.shutdown).start()
            return
        if self.command == 'GET' and self.path == '/api/library':
            return self.answer(200, {'courses': []})
        self.answer(404, {'detail': 'Not Found'})

    do_GET = do_POST = handle_request


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
