#!/usr/bin/env python3
import json, sys, zipfile, re
from pathlib import Path

ZIP_PATH = Path.home() / "Downloads/5e2c9231-3ed0-483c-bac4-fedf5d5c05ee.zip"
JSON_PATH = "ttl/30d/export_data/96e4f10c-358a-40e7-b3be-660cfe21cad2/prod-grok-backend.json"
OUT_PATH  = Path.home() / "aubieeternal_finetune/output/training_data.jsonl"

MIN_WORDS = 20
MAX_WORDS = 800

def word_count(s):
    return len(s.split())

def clean(s):
    return re.sub(r'\n{3,}', '\n\n', s.strip())

def walk_tree(responses_list, leaf_id):
    by_id = {}
    for r in responses_list:
        inner = r.get('response', r)
        rid = inner.get('_id')
        if rid:
            by_id[rid] = inner
    path = []
    cur_id = leaf_id
    seen = set()
    while cur_id and cur_id not in seen:
        seen.add(cur_id)
        node = by_id.get(cur_id)
        if not node:
            break
        path.append(node)
        cur_id = node.get('parent_response_id')
    path.reverse()
    return path

def extract_pairs(conv_item):
    meta      = conv_item['conversation']
    responses = conv_item['responses']
    leaf_id   = meta.get('leaf_response_id')
    if not leaf_id or not responses:
        return []
    path = walk_tree(responses, leaf_id)
    pairs = []
    i = 0
    while i < len(path) - 1:
        a = path[i]
        b = path[i + 1]
        a_sender = a.get('sender', '')
        b_sender = b.get('sender', '')
        a_msg    = clean(a.get('message', ''))
        b_msg    = clean(b.get('message', ''))
        if a_sender == 'human' and b_sender != 'human':
            if (MIN_WORDS <= word_count(a_msg) <= MAX_WORDS and
                MIN_WORDS <= word_count(b_msg) <= MAX_WORDS):
                pairs.append((a_msg, b_msg))
            i += 2
        else:
            i += 1
    return pairs

def main():
    print(f"Loading {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        with zf.open(JSON_PATH) as f:
            data = json.load(f)
    conversations = data['conversations']
    print(f"Total conversations: {len(conversations)}")
    all_pairs = []
    skipped   = 0
    for conv in conversations:
        try:
            pairs = extract_pairs(conv)
            all_pairs.extend(pairs)
        except Exception as e:
            skipped += 1
    print(f"Extracted pairs: {len(all_pairs)}  |  skipped convs: {skipped}")
    with open(OUT_PATH, 'a') as out:
        for user_msg, asst_msg in all_pairs:
            record = {"messages": [{"role": "user", "content": user_msg}, {"role": "assistant", "content": asst_msg}]}
            out.write(json.dumps(record) + '\n')
    print(f"Done — appended {len(all_pairs)} pairs to {OUT_PATH}")

if __name__ == '__main__':
    main()
