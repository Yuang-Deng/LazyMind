import json
import subprocess
import sys
from unittest.mock import patch

import pytest
import lazyllm

from lazyllm.tools.agent import ToolExecutionError
from lazyllm.tools.agent.toolsManager import ToolManager
from lazymind.chat.engine.tools import native_search, local_fs, spotlight


def test_search_enabled_without_read_access(monkeypatch, tmp_path):
    lazyllm.init_session()
    lazyllm.locals['_lazyllm_agent'] = {'workspace': {}}
    lazyllm.globals['agentic_config'] = {}
    monkeypatch.setattr(local_fs, 'native_search_available', lambda: True)
    monkeypatch.setattr(local_fs, 'search_native', lambda *args: {'results': [{'path': str(tmp_path)}]})
    tool = local_fs.LocalFileToolkit()
    assert tool.__key_source__()
    assert tool.search('plan')['results']
    with pytest.raises(ToolExecutionError):
        tool.read(str(tmp_path / 'plan.txt'))
    with pytest.raises(ToolExecutionError):
        tool.string_replace(str(tmp_path / 'plan.txt'), 'a', 'b')
    manager = ToolManager([tool])
    manager._tool_call['get_LocalFileToolkit_methods']({})
    assert 'LocalFileToolkit_search' in {item['function']['name'] for item in manager.tools_description}


def _mock_index(monkeypatch, paths, exit_code=0):
    real = subprocess.Popen
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return real([sys.executable, '-c',
                     f'import os; os.write(1, {bytes(chr(0).join(map(str, paths)), "utf-8")!r} + b"\\0"); '
                     f'raise SystemExit({exit_code})'], **kwargs)
    monkeypatch.setattr(spotlight.subprocess, 'Popen', run)
    monkeypatch.setattr(spotlight.sys, 'platform', 'darwin')
    return commands


def test_system_scope_accepts_outside_home_and_deduplicates(monkeypatch, tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    document = tmp_path / '中文 plan.txt'
    document.write_text('test')
    monkeypatch.setattr(spotlight.Path, 'home', lambda: home)
    commands = _mock_index(monkeypatch, [document, document])
    result = spotlight.search_spotlight('plan')
    assert result['status'] == 'ok'
    assert result['scope'] is None
    assert len(result['results']) == 1
    assert result['results'][0]['path'] == str(document)
    assert result['results'][0]['size'] == 4
    assert '-onlyin' not in commands[0]


def test_macos_failure_is_not_empty_success(monkeypatch):
    _mock_index(monkeypatch, [], 1)
    result = spotlight.search_spotlight('plan')
    assert result['status'] == 'error'
    assert result['stop_reason'] == 'search_error'


def test_unavailable(monkeypatch):
    monkeypatch.setattr(native_search, 'native_search_available', lambda: False)
    assert native_search.search_native('plan')['status'] == 'unavailable'


@pytest.mark.parametrize('kwargs', [{'limit': True}, {'limit': 101}, {'match': 'sql'},
                                    {'query': 'x" OR 1=1'}, {'kind': 'email'}, {'path': 1}])
def test_invalid_input_never_starts_process(kwargs):
    with patch.object(native_search.subprocess, 'Popen') as process:
        with pytest.raises(ValueError):
            native_search.search_native(**({'query': 'plan'} | kwargs))
        process.assert_not_called()


def test_windows_data_transport_and_partial_results(monkeypatch, tmp_path):
    hit = tmp_path / '中文.txt'
    hit.write_text('x')
    monkeypatch.setattr(native_search.sys, 'platform', 'win32')
    monkeypatch.setattr(native_search, 'native_search_available', lambda: True)
    monkeypatch.setattr(native_search.shutil, 'which', lambda _: 'powershell.exe')
    calls = []

    def output(command, payload):
        calls.append((command, json.loads(payload)))
        return json.dumps({'path': str(hit), 'title': hit.name}).encode() + b'\n{"path":', 'timeout'
    monkeypatch.setattr(native_search, '_windows_output', output)
    result = native_search.search_native("O'Brien", path=str(tmp_path))
    assert result['status'] == 'partial'
    assert result['results'][0]['path'] == str(hit)
    assert "O'Brien" not in ' '.join(calls[0][0])
    assert calls[0][1]['query'] == "O'Brien"


def test_bounded_subprocess_timeout(monkeypatch):
    monkeypatch.setattr(native_search, '_TIMEOUT', 0.05)
    raw, reason = native_search._windows_output(
        [sys.executable, '-c', 'import time; time.sleep(5)'], b'{}')
    assert reason == 'timeout'
    assert raw == b''


def test_bounded_subprocess_output(monkeypatch):
    monkeypatch.setattr(native_search, '_MAX_OUTPUT', 8192)
    _, reason = native_search._windows_output(
        [sys.executable, '-c', 'import os; os.write(1, b"x"*100000)'], b'{}')
    assert reason == 'output_limit'
