#!/usr/bin/env python3
"""Run the actual native-search tool without an LLM, index build, or deployment.

Run with this checkout's algorithm + algorithm/lazyllm on PYTHONPATH.
Feishu reads an existing user's access token from FEISHU_USER_ACCESS_TOKEN.
This script does not acquire credentials or change connection settings.
"""
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', choices=['local', 'feishu'])
    parser.add_argument('query')
    parser.add_argument('--path', default='')
    parser.add_argument('--match', choices=['name', 'content', 'either'], default='either')
    parser.add_argument('--kind', choices=['any', 'file', 'directory'], default='any')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--page-token', default='')
    args = parser.parse_args()
    import lazyllm
    with lazyllm.new_session():
        if args.source == 'local':
            from lazymind.chat.engine.tools.local_fs import LocalFileToolkit
            result = LocalFileToolkit().search(args.query, args.match, args.path, args.kind, args.limit)
        else:
            token = os.environ.get('FEISHU_USER_ACCESS_TOKEN', '').strip()
            if not token:
                parser.error('set FEISHU_USER_ACCESS_TOKEN to an existing connected user access token')
            from lazymind.chat.engine.tool_auth import inject_tool_config
            from lazyllm.tools.fs.supplier.feishu import FeishuFS
            inject_tool_config({'feishu': token})
            result = FeishuFS(space_id='dynamic', dynamic_auth=True).search_documents(
                args.query, args.limit, args.page_token)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
