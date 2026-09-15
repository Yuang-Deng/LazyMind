#!/usr/bin/env python3
"""Run the opt-in PoC Spotlight host on macOS; only /search is exposed.

Set LAZYMIND_SPOTLIGHT_TOKEN to a random secret. Defaults to loopback; a
container pilot can explicitly bind an address reachable from its bridge.
Reads of matching files remain with LazyMind's authorized local file tools.
"""
from __future__ import annotations

import argparse
import hmac
import importlib.util
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

MODULE = Path(__file__).resolve().parents[2] / 'algorithm/lazymind/chat/engine/tools/spotlight.py'
spec = importlib.util.spec_from_file_location('spotlight_host_search', MODULE)
spotlight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spotlight)
slots = threading.BoundedSemaphore(2)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Do not log tokens, query text or discovered private paths.

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def respond(self, status, result):
        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        expected = 'Bearer ' + os.environ['LAZYMIND_SPOTLIGHT_TOKEN']
        if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
            self.respond(401, {'status': 'unauthorized'})
            return
        if self.path != '/search':
            self.respond(404, {'status': 'not_found'})
            return
        acquired = False
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('invalid request size')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) - {'query', 'match', 'path', 'kind', 'limit'}:
                raise ValueError('invalid search arguments')
            # Keep the legacy experimental bridge home-scoped, even though the
            # native toolkit now searches the full system index by default.
            home = Path.home().resolve()
            scope = Path(payload.get('path') or home).expanduser().resolve()
            if not scope.is_relative_to(home):
                raise ValueError('path must stay inside the host home directory')
            payload['path'] = str(scope)
            acquired = slots.acquire(blocking=False)
            if not acquired:
                self.respond(429, {'status': 'busy'})
                return
            self.respond(200, spotlight.search_spotlight(**payload))
        except (ValueError, TypeError) as exc:
            self.respond(400, {'status': 'invalid_request', 'reason': str(exc)})
        except OSError:
            self.respond(503, {'status': 'unavailable'})
        finally:
            if acquired:
                slots.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=19093)
    args = parser.parse_args()
    if len(os.environ.get('LAZYMIND_SPOTLIGHT_TOKEN', '')) < 32:
        parser.error('LAZYMIND_SPOTLIGHT_TOKEN must contain at least 32 random characters')
    if spotlight.sys.platform != 'darwin':
        parser.error('run this host on macOS')
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
