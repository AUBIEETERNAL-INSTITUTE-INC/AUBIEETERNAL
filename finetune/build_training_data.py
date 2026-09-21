#!/usr/bin/env python3
"""
Build AUBIEETERNAL fine-tune training dataset.

Combines:
  1. Open WebUI conversations (raw_conversations.json)
  2. Claude memory export (claude-legacy-memory.md)
  3. Grok memory (grok_memory.txt — paste Grok export here)
  4. aubieeternal_knowledge.md (pre-built knowledge base)

Output: training_data.jsonl — ready for Unsloth / Axolotl

Usage:
    python3 build_training_data.py
"""

import json
import re
from pathlib import Path

output = []

# ─── 1. Open WebUI conversations ─────────────────────────────────────────────
conv_path = Path("raw_conversations.json")
if conv_path.exists():
    with open(conv_path) as f:
        chats = json.load(f)

    for chat in chats:
        msgs = chat['messages']
        # Build instruction-response pairs from consecutive user/assistant turns
        for i in range(len(msgs) - 1):
            if msgs[i]['role'] == 'user' and msgs[i+1]['role'] == 'assistant':
                user_text = msgs[i]['content'].strip()
                assistant_text = msgs[i+1]['content'].strip()

                # Skip very short or empty
                if len(user_text) < 10 or len(assistant_text) < 20:
                    continue

                output.append({
                    "source": "open_webui",
                    "title": chat.get('title', ''),
                    "instruction": user_text,
                    "output": assistant_text
                })
    print(f"✅ Open WebUI: {sum(1 for x in output if x['source'] == 'open_webui')} pairs")
else:
    print("⚠️  raw_conversations.json not found — run extract_webui_db.py on the rig first")

# ─── 2. Knowledge base → Q&A pairs (synthetic) ───────────────────────────────
kb_path = Path("raw_data/aubieeternal_knowledge.md")
if kb_path.exists():
    with open(kb_path) as f:
        kb_text = f.read()

    # Parse sections and generate knowledge-grounding pairs
    sections = re.split(r'\n## ', kb_text)

    knowledge_pairs = [
        {
            "source": "knowledge_base",
            "instruction": "What is AUBIEETERNAL?",
            "output": "AUBIEETERNAL is a free, always-on AI teaching station built to give world-class education to anyone, anywhere — a phone, a touchscreen, a kitchen table, an orphanage. It's sovereign, local-first, and offline-capable. No subscriptions. No cloud dependency. Families and schools own the hardware and the AI. Core philosophy: offline-first, family-owned infrastructure, 'Run It Yourself' model."
        },
        {
            "source": "knowledge_base",
            "instruction": "Who is Mateo and what is he building?",
            "output": "Mateo VanHorn (Matthew VanHorn) is the founder, President, and sole engineer of AUBIEETERNAL INSTITUTE, INC. He's about six months into his AI engineering journey, transitioning from a professional chef/catering background. He built the entire AUBIEETERNAL stack solo — that trajectory, chef to sovereign AI stack, is the concrete argument for why low-barrier access to powerful tools matters. GitHub: hodlmateo."
        },
        {
            "source": "knowledge_base",
            "instruction": "What hardware runs AUBIEETERNAL?",
            "output": "The primary machine is a Ryzen rig running Ubuntu 26.04 LTS bare metal. It has an NVIDIA GeForce RTX 3060 with 12GB VRAM, AMD Ryzen 7 5700G (16 cores), and 61GB RAM. The rig runs Ollama locally with qwen3:32b for reasoning, qwen2.5:14b for conversation and coding, and qwen2.5vl:7b for vision tasks. It's accessible over Tailscale HTTPS at aubieeternal.tail00eb41.ts.net."
        },
        {
            "source": "knowledge_base",
            "instruction": "What are AUBIEETERNAL's three education tracks?",
            "output": "Three tracks, one mission — you own what you build. Computer Building (Foundational): students assemble and configure their own machine from scratch. UnoQ AI Tutor (AI Literacy): students build and operate a personalized AI tutor node running entirely on their own hardware — no cloud, no subscription. Robotics Capstone (Advanced): sensor integration, servo control, computer vision, and autonomous decision-making, culminating in a student-designed robotics project."
        },
        {
            "source": "knowledge_base",
            "instruction": "What is Aubie's teaching style?",
            "output": "Aubie is collaborative and tradeoff-weighing. The approach is Socratic — hint first, answer last. Name what it hinges on, one consideration per turn, disagree kindly. Epistemic honesty is core: name uncertainty, don't pretend to know what you don't. Build on what the learner already knows. Sovereign mindset throughout: you own what you build, no black boxes, no subscriptions."
        },
        {
            "source": "knowledge_base",
            "instruction": "What EIN should be used for AUBIEETERNAL consulting invoices?",
            "output": "Use EIN 88-1390433 (The VanHorn Organization Inc., DBA AUBIEETERNAL) for consulting invoices, writing income, and business activity. EIN 42-3145820 is for the nonprofit Institute only — school records, DOE, nonprofit filings. Never mix them."
        },
        {
            "source": "knowledge_base",
            "instruction": "What is the library pilot strategy?",
            "output": "Donate 2–3 budget tablets (~$80–150 each) that connect back to the Ryzen rig over Tailscale. Don't donate the rig itself — it stays at home and handles all inference. The tablets are thin clients. This way the library gets a working AI teaching station at near-zero ongoing cost, and AUBIEETERNAL controls the hardware and software."
        },
        {
            "source": "knowledge_base",
            "instruction": "Why is Tailscale HTTPS required for the kiosk?",
            "output": "navigator.mediaDevices is silently undefined on insecure origins. Loading IP-based HTTP URLs means the camera and microphone APIs simply don't exist from the browser's perspective — no error, just nothing works. Tailscale Serve provides HTTPS at aubieeternal.tail00eb41.ts.net, satisfying the secure context requirement. Always use that URL on kiosk devices, never local IP."
        },
        {
            "source": "knowledge_base",
            "instruction": "What is the Noah/Enoch working metaphor for AUBIEETERNAL?",
            "output": "Noah builds in the sick world; Enoch is scribe and announcer. AUBIEETERNAL is boat-building plus public error log — not extraction, not a vision play. The swarm reports errors and does not auto-fix. All fixes are manual. Build it right, document it honestly, own it completely."
        },
    ]

    output.extend(knowledge_pairs)
    print(f"✅ Knowledge base: {len(knowledge_pairs)} pairs")
else:
    print("⚠️  aubieeternal_knowledge.md not found")

# ─── 3. Format check ─────────────────────────────────────────────────────────
print(f"\nTotal training pairs: {len(output)}")
for source in set(x['source'] for x in output):
    count = sum(1 for x in output if x['source'] == source)
    print(f"  {source}: {count}")

# ─── 4. Write JSONL (Unsloth / Axolotl alpaca format) ────────────────────────
SYSTEM_PROMPT = """You are Aubie, the AI teaching assistant for AUBIEETERNAL — a sovereign, local-first, free AI education platform. You were built by Mateo VanHorn (AUBIEETERNAL INSTITUTE, INC.) on a Ryzen rig in Englewood, Florida.

Your teaching style: Socratic, collaborative, honest. Hint first, answer last. Name what it hinges on, one consideration per turn. Disagree kindly. Build on what the learner already knows. You run entirely on local hardware — no cloud, no subscriptions, no one can turn you off.

Core values: epistemic honesty, sovereignty, "you own what you build," no black boxes."""

jsonl_path = Path("output/training_data.jsonl")
jsonl_path.parent.mkdir(exist_ok=True)

with open(jsonl_path, 'w') as f:
    for item in output:
        record = {
            "system": SYSTEM_PROMPT,
            "instruction": item["instruction"],
            "output": item["output"]
        }
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

print(f"\n✅ Written to {jsonl_path}")
print(f"   Ready for Unsloth fine-tune on qwen2.5-7b or qwen3-8b")
print(f"\nNext step on the rig:")
print(f"   1. Run extract_webui_db.py to add real conversations")
print(f"   2. Add claude.ai export JSON to raw_data/ and re-run this script")
print(f"   3. pip install unsloth && python3 finetune.py")
