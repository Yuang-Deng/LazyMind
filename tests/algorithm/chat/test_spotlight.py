from unittest.mock import patch
import subprocess
import sys

import lazyllm
import pytest
from lazyllm.tools.agent import ToolExecutionError

from lazymind.chat.engine.tools import spotlight
from lazymind.chat.engine.tools.local_file import resolver, workspace


@pytest.mark.parametrize('query', ['*', 'x" || kMDItemFSName == "*', 'x\n', '', 'a' * 257])
def test_search_rejects_query_language_injection(query, monkeypatch):
    monkeypatch.setattr(spotlight.sys, 'platform', 'darwin')
    with patch.object(spotlight.subprocess, 'Popen') as process:
        with pytest.raises(ValueError):
            spotlight.search_spotlight(query)
        process.assert_not_called()


def test_search_rejects_missing_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(spotlight.sys, 'platform', 'darwin')
    with pytest.raises(ValueError, match='existing directory'):
        spotlight.search_spotlight('LazyMind', path=str(tmp_path / 'missing'))


def test_results_are_bounded_and_symlink_escape_is_filtered(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    outside = tmp_path / 'private.txt'
    outside.write_text('private')
    escape = home / 'escape'
    escape.symlink_to(outside)
    files = [home / f'{i}.txt' for i in range(4)]
    for path in files:
        path.write_text('indexed text')
    paths = [str(escape), *map(str, files)]
    real_popen = subprocess.Popen
    commands = []

    def index_process(command, **kwargs):
        commands.append(command)
        return real_popen([sys.executable, '-c',
                           f'import os; os.write(1, {chr(0).join(paths).encode()!r} + b"\\0")'], **kwargs)

    monkeypatch.setattr(spotlight.sys, 'platform', 'darwin')
    monkeypatch.setattr(spotlight.Path, 'home', lambda: home)
    monkeypatch.setattr(spotlight.subprocess, 'Popen', index_process)
    result = spotlight.search_spotlight('indexed', path=str(home), limit=2)
    assert result['status'] == 'partial'
    assert result['stop_reason'] == 'result_limit'
    assert [r['path'] for r in result['results']] == list(map(str, files[:2]))
    assert commands[0][:4] == ['/usr/bin/mdfind', '-0', '-onlyin', str(home)]


def test_tool_is_owner_bound_even_when_called_directly(monkeypatch):
    monkeypatch.setenv('LAZYMIND_SPOTLIGHT_USER_ID', 'owner')
    monkeypatch.setenv('LAZYMIND_SPOTLIGHT_URL', 'http://localhost/search')
    monkeypatch.setenv('LAZYMIND_SPOTLIGHT_TOKEN', 'test-secret')
    with lazyllm.new_session():
        lazyllm.globals['agentic_config'] = {'user_id': 'another-user'}
        tool = spotlight.SpotlightToolkit()
        assert not tool.__key_source__()
        assert tool.search_spotlight('LazyMind')['status'] == 'unavailable'


def test_authorized_document_reuses_reader_but_blocks_symlink_and_extension(tmp_path, monkeypatch):
    home, work = tmp_path / 'source', tmp_path / 'workspace'
    home.mkdir()
    work.mkdir()
    document = home / 'slides.pptx'
    document.write_bytes(b'fixture')
    outside = tmp_path / 'outside.pptx'
    outside.write_bytes(b'private')
    (home / 'escape.pptx').symlink_to(outside)
    (home / 'secret.txt').write_text('private')
    monkeypatch.setattr(workspace, 'chat_agent_workspace', lambda *_: str(work))
    monkeypatch.setattr(resolver, 'resolve_attachment_path', lambda *_: (None, ''))
    monkeypatch.setattr(resolver, '_known_attachment_realpaths', lambda: set())
    monkeypatch.setattr(resolver, '_workflow_workspace_target', lambda *_, **__: None)
    config = {'user_id': 'owner', 'conversation_id': 'poc', 'local_fs_sources': [
        {'source_id': 'poc', 'paths': [str(home)], 'file_extensions': ['pptx']},
    ]}
    with lazyllm.new_session():
        lazyllm.globals['agentic_config'] = config
        with patch.object(resolver, '_resolved_from_local_file', return_value='parsed') as reader:
            assert resolver.resolve_text_target(str(document)) == 'parsed'
            assert reader.call_args.args[0] == str(document)
            reader.reset_mock()
            for path in [home / 'escape.pptx', home / 'secret.txt']:
                with pytest.raises(ToolExecutionError):
                    resolver.resolve_text_target(str(path))
            reader.assert_not_called()
        own_file = work / 'notes.txt'
        own_file.write_text('workspace text')
        assert resolver.resolve_text_target(str(own_file)).path == str(own_file)
        assert resolver.resolve_text_target(str(work), allow_directory=True).path == str(work)
