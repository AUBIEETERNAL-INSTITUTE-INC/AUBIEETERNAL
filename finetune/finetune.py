#!/usr/bin/env python3
import os, json, torch
from torch.utils.data import Dataset
os.environ["TOKENIZERS_PARALLELISM"] = "false"

with open("output/training_data.jsonl") as f:
    records = [json.loads(l) for l in f if l.strip()]
print(f"Loaded {len(records)} records")

texts = [
    f"<|im_start|>system\n{r['system']}<|im_end|>\n"
    f"<|im_start|>user\n{r['instruction']}<|im_end|>\n"
    f"<|im_start|>assistant\n{r['output']}<|im_end|>"
    for r in records
]

from unsloth import FastLanguageModel
print("Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct",
    max_seq_length=2048, load_in_4bit=True, dtype=None,
)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    bias="none", use_gradient_checkpointing="unsloth", random_state=42, use_rslora=False,
)
print("LoRA applied")

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

print("Tokenizing...")
enc = tokenizer(texts, truncation=True, max_length=2048, padding="max_length", return_tensors="pt")

class AubieDataset(Dataset):
    def __init__(self, enc):
        self.ids = enc["input_ids"]; self.mask = enc["attention_mask"]
    def __len__(self): return len(self.ids)
    def __getitem__(self, i):
        return {"input_ids": self.ids[i], "attention_mask": self.mask[i], "labels": self.ids[i].clone()}

dataset = AubieDataset(enc)
print(f"Dataset: {len(dataset)} examples")

from transformers import Trainer, TrainingArguments
N, BATCH, GA, EP = len(dataset), 2, 4, 3
MAX_STEPS = max(EP, (N // (BATCH*GA)) * EP)
print(f"max_steps={MAX_STEPS}")

trainer = Trainer(
    model=model,
    args=TrainingArguments(
        per_device_train_batch_size=BATCH, gradient_accumulation_steps=GA,
        max_steps=MAX_STEPS, learning_rate=2e-4, bf16=True,  # Ampere supports bf16, logging_steps=1,
        optim="adamw_8bit", weight_decay=0.01, lr_scheduler_type="linear",
        warmup_steps=max(1, MAX_STEPS//10), seed=42,
        output_dir="output/checkpoints", save_strategy="no", report_to="none",
        dataloader_num_workers=0, remove_unused_columns=False,
    ),
    train_dataset=dataset,
)

print("Training...")
trainer.train()

model.save_pretrained("output/aubie_lora")
tokenizer.save_pretrained("output/aubie_lora")
print("\n✅ LoRA saved → output/aubie_lora/")
