#!/usr/bin/env python3
"""Exercise the real LazyMind main ChatAgent, without frontend or model mocks.

Run in the existing algorithm Python environment, with its model/service env.
Set LAZYMIND_SKILL_FS_URL to this checkout's skills/search directory. Spotlight
requires LAZYMIND_SPOTLIGHT_URL, TOKEN and USER_ID. Cloud MCP config is optional
and read from a private JSON file; credentials are never written into results.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import time
import uuid

CASES = {
    'code': '请查找 LazyMind 本地源码，说明 Chat 如何限制可读取的本地目录。请实际搜索并阅读代码，给出文件出处。',
    'ppt': '请在本地找到半年工作总结的 PPT，阅读并说明里面如何描述 LazyMind 的工作，给出文件出处。',
    'feishu': '请在已连接的飞书里查找正文提到 LazyMind 的文档，读取后概括内容，并给出文档链接。',
    'xlsx-gap': '请在本地检索单元格正文包含 baseline_rank_ic 的 Excel 工作簿。若未命中，准确说明检索范围和结论边界。',
}


async def run(args):
    import lazyllm
    from lazymind.chat.service.chat_request import ChatRequest
    from lazymind.chat.service.chat_service import handle_chat
    from lazymind.chat.service.component.tool_registry import DEFAULT_TOOLS

    mcp_config = json.loads(Path(args.mcp_config).read_text()) if args.mcp_config else []
    history = []
    if args.resume_events:
        # Chat accepts product messages containing tool tags, not provider tool-role messages.
        content = []
        for line in Path(args.resume_events).read_text().splitlines():
            for raw in json.loads(line)['chunk'].split('\n\n'):
                if raw.strip():
                    content.append(json.loads(raw).get('data', {}).get('text') or '')
        history = [{'role': 'user', 'content': CASES[args.case]},
                   {'role': 'assistant', 'content': ''.join(content)}]
        from lazymind.chat.service.component.history import normalize_history_for_agent
        if not any(m.get('role') == 'tool' for m in normalize_history_for_agent(history)):
            raise ValueError('Recovery input contains no complete Chat tool exchanges')
    request = ChatRequest(
        message={'query': CASES[args.case], 'history': history},
        conversation={'user_id': args.user_id, 'session_id': str(uuid.uuid4()),
                      'conversation_id': 'enterprise-search-poc-' + str(uuid.uuid4())},
        retrieval={'filters': {}, 'local_fs_sources': [
            {'source_id': f'poc-{i}', 'paths': [str(Path(path).resolve())],
             'file_extensions': ['py', 'go', 'ts', 'tsx', 'md', 'txt', 'pptx', 'xlsx', 'docx', 'pdf']}
            for i, path in enumerate(args.scope)
        ]},
        runtime={'mcp_config': mcp_config, 'thinking_depth': 'medium'},
        personalization={'use_memory': False},
        agent={'available_skills': ['enterprise-search'], 'enable_subagent': False,
               'disabled_tools': [cfg.name for cfg in DEFAULT_TOOLS
                                  if cfg.name != 'spotlight']},
        workflow={'enable_workflow': False},
        explicit_resource_bindings={'skill_names': ['enterprise-search']},
    )
    started = time.monotonic()
    chunks = []
    secrets = [os.environ.get('LAZYMIND_SPOTLIGHT_TOKEN', '')]
    for server in mcp_config:
        secrets.extend(str(v) for v in server.get('headers', {}).values())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    events_path = output.with_suffix('.events.jsonl')
    with events_path.open('w') as events, lazyllm.new_session(request.conversation.session_id):
        events_path.chmod(0o600)
        response = await handle_chat(request)
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for secret in secrets:
                if secret:
                    text = text.replace(secret, '[REDACTED]')
            chunks.append(text)
            events.write(json.dumps({'chunk': text}, ensure_ascii=False) + '\n')
            events.flush()
    stream = ''.join(chunks)
    result = {'case': args.case, 'query': CASES[args.case],
              'elapsed_seconds': round(time.monotonic() - started, 2),
              'entrypoint': 'lazymind.chat.service.chat_service.handle_chat',
              'resumed_from_history': bool(history),
              'scopes': args.scope, 'stream': stream}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    output.chmod(0o600)
    print(json.dumps({k: v for k, v in result.items() if k != 'stream'}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--user-id', required=True)
    parser.add_argument('--scope', action='append', default=[],
                        help='Already authorized read directory; not in the user query')
    parser.add_argument('--mcp-config', help='Private JSON file containing existing MCP server configs')
    parser.add_argument('--resume-events', help='Original .events.jsonl for a labeled recovery run')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
