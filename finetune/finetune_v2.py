#!/usr/bin/env python3
"""
AUBIEETERNAL fine-tune — Round 4+
Key fix vs. v1: loss is masked to ASSISTANT RESPONSE TOKENS ONLY.
In v1, loss was computed over the full sequence (system + user + assistant),
which wasted most of the gradient signal on tokens we don't want to learn.
This version sets labels=-100 for every prompt token so only the assistant
response drives the weight updates.

Also fixed: proper EOS token appended so model knows when to stop talking.
"""

import json
import torch
from torch.utils.data import Dataset
from transformers import TrainingArguments, Trainer, DataCollatorWithPadding
from unsloth import FastLanguageModel

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME   = "output/aubie_merged" # load from MERGED weights (not the LoRA adapter dir)
                                     # Using aubie_lora here fails because Unsloth won't let
                                     # you call get_peft_model() on a model that already has
                                     # LoRA adapters loaded. aubie_merged is the clean base.
DATA_FILE   = "output/training_data_r10.jsonl"
OUTPUT_DIR  = "output/aubie_lora_r10"
MAX_SEQ_LEN  = 1024
NUM_EPOCHS   = 5                     # up from 3; masking makes each step count more
BATCH_SIZE   = 2
GRAD_ACCUM   = 4                     # effective batch = 8
LR           = 2e-4
# ─────────────────────────────────────────────────────────────────────────────


def build_chatml(system: str, instruction: str, output: str) -> tuple[str, str]:
    """
    Returns (full_text, prompt_only).
    full_text  = everything the model sees, including the response + EOS.
    prompt_only = everything up to (and including) '<|im_start|>assistant\n'
                  so we know how many tokens to mask.
    """
    prompt = (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{instruction}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    # Append response + end token so the model learns to stop
    full = prompt + output + "<|im_end|>"
    return full, prompt


class AubieDataset(Dataset):
    def __init__(self, path: str, tokenizer, max_len: int):
        self.samples = []
        with open(path) as f:
            raw = [json.loads(l) for l in f if l.strip()]
            for ex in raw:
                if "messages" in ex:
                    ex["system"] = ""
                    ex["instruction"] = ex["messages"][0]["content"]
                    ex["output"] = ex["messages"][1]["content"]

        print(f"Loaded {len(raw)} records")

        for ex in raw:
            full_text, prompt_text = build_chatml(
                ex["system"], ex["instruction"], ex["output"]
            )

            # Tokenize full sequence
            full_enc = tokenizer(
                full_text,
                truncation=True,
                max_length=max_len,
                padding=False,
                return_tensors=None,
            )
            input_ids = full_enc["input_ids"]
            attention_mask = full_enc["attention_mask"]

            # Tokenize prompt only to find where response starts
            prompt_enc = tokenizer(
                prompt_text,
                truncation=True,
                max_length=max_len,
                padding=False,
                return_tensors=None,
            )
            prompt_len = len(prompt_enc["input_ids"])

            # Labels: -100 for prompt tokens, real ids for response tokens
            # This is the critical fix — gradient only flows through the response
            labels = [-100] * len(input_ids)
            for i in range(prompt_len, len(input_ids)):
                labels[i] = input_ids[i]

            # Skip examples where the response is completely truncated
            if all(l == -100 for l in labels):
                print(f"  WARNING: skipping truncated example: {ex['instruction'][:60]}")
                continue

            self.samples.append({
                "input_ids":      torch.tensor(input_ids,      dtype=torch.long),
                "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
                "labels":         torch.tensor(labels,         dtype=torch.long),
            })

        print(f"Dataset: {len(self.samples)} usable examples after masking check")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]


class PaddingCollator:
    """Pads a batch of variable-length tensors to the same length."""
    def __init__(self, pad_token_id: int):
        self.pad_id = pad_token_id

    def __call__(self, features):
        max_len = max(f["input_ids"].size(0) for f in features)
        input_ids      = []
        attention_mask = []
        labels         = []

        for f in features:
            seq_len = f["input_ids"].size(0)
            pad_len = max_len - seq_len

            input_ids.append(torch.cat([
                f["input_ids"],
                torch.full((pad_len,), self.pad_id, dtype=torch.long)
            ]))
            attention_mask.append(torch.cat([
                f["attention_mask"],
                torch.zeros(pad_len, dtype=torch.long)
            ]))
            labels.append(torch.cat([
                f["labels"],
                torch.full((pad_len,), -100, dtype=torch.long)  # don't learn from padding
            ]))

        return {
            "input_ids":      torch.stack(input_ids),
            "attention_mask": torch.stack(attention_mask),
            "labels":         torch.stack(labels),
        }


def main():
    print("Loading model from last LoRA checkpoint...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        MODEL_NAME,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=True,
        dtype=torch.bfloat16,
    )

    # Re-apply LoRA for continued training
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                         "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    dataset = AubieDataset(DATA_FILE, tokenizer, MAX_SEQ_LEN)
    collator = PaddingCollator(pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)

    steps_per_epoch = max(1, len(dataset) // (BATCH_SIZE * GRAD_ACCUM))
    max_steps = steps_per_epoch * NUM_EPOCHS
    print(f"max_steps={max_steps}  ({steps_per_epoch} steps/epoch × {NUM_EPOCHS} epochs)")

    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        max_steps=max_steps,
        learning_rate=LR,
        bf16=True,
        fp16=False,
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        warmup_steps=max(1, max_steps // 10),
        save_steps=max_steps,          # save once at the end
        save_total_limit=1,
        report_to="none",
        dataloader_num_workers=0,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset,
        data_collator=collator,
    )

    print("Training with RESPONSE-ONLY loss masking...")
    trainer.train()

    print(f"\nSaving LoRA → {OUTPUT_DIR}/")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("Done.")


if __name__ == "__main__":
    main()
