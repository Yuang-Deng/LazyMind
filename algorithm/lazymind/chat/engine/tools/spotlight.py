"""macOS system-index discovery plus the legacy owner-bound PoC bridge client.

The native query reads metadata only; the experimental bridge retains its own scope.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
import selectors
import subprocess
import sys
import time
import urllib.error
import urllib.request


def search_spotlight(query: str, match: str = 'content', path: str = '',
                     kind: str = 'any', limit: int = 30) -> dict:
    """Query the current macOS user's Spotlight index with bounded output."""
    if sys.platform != 'darwin':
        return {'status': 'unavailable', 'reason': 'Spotlight requires a macOS host'}
    if not isinstance(query, str) or not query.strip() or len(query) > 256:
        raise ValueError('query must contain 1–256 characters')
    if any(ord(c) < 32 or c in '*?"\\' for c in query):
        raise ValueError('use literal keywords without wildcards, quotes or control characters')
    if match not in {'name', 'content', 'either'} or kind not in {'any', 'file', 'directory'}:
        raise ValueError('invalid match or kind')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    scope = Path(path).expanduser().resolve() if path else None
    if scope is not None and not scope.is_dir():
        raise ValueError('path must be an existing directory')
    value = f'"*{query.strip()}*"cd'
    expressions = {'name': f'kMDItemFSName == {value}',
                   'content': f'kMDItemTextContent == {value}'}
    expression = expressions.get(match) or f'({expressions["name"]} || {expressions["content"]})'
    if kind != 'any':
        operator = '==' if kind == 'directory' else '!='
        expression += f' && kMDItemContentType {operator} "public.folder"'
    started = time.monotonic()
    results, seen = [], set()
    stopped, pending, received = 'finished', b'', 0
    command = ['/usr/bin/mdfind', '-0']
    if scope is not None:
        command += ['-onlyin', str(scope)]
    command.append(expression)
    with subprocess.Popen(command,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = 8 - (time.monotonic() - started)
                    if remaining <= 0:
                        stopped = 'timeout'
                        break
                    if not selector.select(remaining):
                        stopped = 'timeout'
                        break
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > 1024 * 1024:
                        stopped = 'output_limit'
                        break
                    parts = (pending + chunk).split(b'\0')
                    pending = parts.pop()
                    for raw in parts:
                        if not raw:
                            continue
                        try:
                            candidate = Path(os.fsdecode(raw)).resolve()
                            if (scope is not None and not candidate.is_relative_to(scope)) or not candidate.exists():
                                continue
                        except (OSError, ValueError, RuntimeError):
                            continue
                        if candidate in seen:
                            continue
                        seen.add(candidate)
                        if len(results) >= limit:
                            stopped = 'result_limit'
                            break
                        results.append({'path': str(candidate), 'title': candidate.name,
                                        'kind': 'directory' if candidate.is_dir() else 'file',
                                        'source': 'local', 'backend': 'spotlight', 'match': match})
                        try:
                            stat = candidate.stat()
                            results[-1].update(size=stat.st_size, modified_at=datetime.fromtimestamp(
                                stat.st_mtime, timezone.utc).isoformat())
                        except OSError:
                            pass
                    if stopped != 'finished':
                        break
        finally:
            if process.poll() is None:
                if stopped != 'finished':
                    process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    stopped = 'timeout'
        if stopped == 'finished' and process.returncode:
            stopped = 'search_error'
    status = 'ok' if stopped == 'finished' else ('partial' if results else 'error')
    return {'status': status, 'query': query,
            'scope': str(scope) if scope is not None else None, 'backend': 'spotlight',
            'results': results, 'stop_reason': stopped,
            'elapsed_ms': round((time.monotonic() - started) * 1000),
            'coverage': 'Spotlight index only; empty results do not prove absence. '
                        'Discovery does not grant permission to read a file.'}


class SpotlightToolkit:
    """Discover indexed local files and directories without reading their content."""

    __public_apis__ = ['search_spotlight']

    def __key_source__(self):
        import lazyllm
        config = lazyllm.globals.get('agentic_config') or {}
        owner = os.environ.get('LAZYMIND_SPOTLIGHT_USER_ID', '')
        return bool(owner and config.get('user_id') == owner
                    and os.environ.get('LAZYMIND_SPOTLIGHT_URL')
                    and os.environ.get('LAZYMIND_SPOTLIGHT_TOKEN'))

    def search_spotlight(self, query: str, match: str = 'content', path: str = '',
                         kind: str = 'any', limit: int = 30) -> dict:
        """Search the macOS home index for literal keywords, including source code.

        Args:
            query: A short keyword or code symbol, not a natural-language question.
            match: content for body search, name for filename discovery, or either.
            path: Optional previously discovered directory; empty searches the user's home.
            kind: any, file, or directory.
            limit: Maximum results, from 1 to 100. Results may be truncated.

        Returns:
            File paths and explicit index coverage; use existing authorized read tools next.
        """
        if not self.__key_source__():
            return {'status': 'unavailable', 'reason': 'No Spotlight host is connected for this user'}
        request = urllib.request.Request(
            os.environ['LAZYMIND_SPOTLIGHT_URL'],
            data=json.dumps(dict(query=query, match=match, path=path, kind=kind, limit=limit)).encode(),
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + os.environ['LAZYMIND_SPOTLIGHT_TOKEN']},
            method='POST',
        )
        # Never follow a redirect carrying the host bearer credential.

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=12) as response:
                return json.loads(response.read(1024 * 1024))
        except (OSError, ValueError):
            return {'status': 'unavailable', 'reason': 'Spotlight host request failed; coverage is unknown'}
