#!/usr/bin/env python3
import sqlite3, json, sys, glob
from pathlib import Path

DB_PATH = Path("/home/aubieeternal/.cache/uv/archive-v0/GZdtKubGA3PMwmh7/lib/python3.11/site-packages/open_webui/data/webui.db")
if not DB_PATH.exists():
    dbs = glob.glob("/home/aubieeternal/.cache/uv/archive-v0/*/lib/python3.11/site-packages/open_webui/data/webui.db")
    if not dbs: print("ERROR: No webui.db found."); sys.exit(1)
    DB_PATH = Path(sorted(dbs, key=lambda p: Path(p).stat().st_size, reverse=True)[0])

print(f"Reading: {DB_PATH} ({DB_PATH.stat().st_size // 1024}KB)")
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
chats = conn.execute("SELECT id, title, chat, created_at, updated_at FROM chat ORDER BY updated_at DESC").fetchall()
print(f"Found {len(chats)} chats")

results = []
for row in chats:
    try:
        data = json.loads(row['chat'])
        hist = data.get('history', {})
        msg_map = hist.get('messages', {})  # {id: {role, content, parentId, childrenIds}}

        if not msg_map:
            continue

        # Find root message (parentId is null or missing)
        root = next((m for m in msg_map.values() if not m.get('parentId')), None)
        if not root:
            continue

        # Walk the primary branch (always take first child)
        clean_messages = []
        current = root
        while current:
            role = current.get('role', '')
            content = current.get('content', '')
            if isinstance(content, list):
                content = ' '.join(p.get('text','') for p in content if isinstance(p,dict) and p.get('type')=='text').strip()
            if content and role in ('user', 'assistant'):
                clean_messages.append({'role': role, 'content': str(content).strip()})
            children = current.get('childrenIds', [])
            current = msg_map.get(children[0]) if children else None

        roles = set(m['role'] for m in clean_messages)
        if 'user' in roles and 'assistant' in roles and len(clean_messages) >= 2:
            results.append({'id': row['id'], 'title': row['title'], 'messages': clean_messages,
                           'created_at': row['created_at'], 'updated_at': row['updated_at']})
    except Exception as e:
        print(f"  Skipping {row['id']}: {e}")

conn.close()
with open("raw_conversations.json", 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n✅ Extracted {len(results)} usable chats → raw_conversations.json")
print(f"   Total messages: {sum(len(c['messages']) for c in results)}")
