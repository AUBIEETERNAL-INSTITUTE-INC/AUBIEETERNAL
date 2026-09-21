from unsloth import FastLanguageModel

LORA = "output/aubie_lora_r9"
OUT  = "output/aubie_merged_r9"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = LORA,
    max_seq_length = 1024,
    load_in_4bit   = True,
)
model.save_pretrained_merged(OUT, tokenizer, save_method="merged_16bit")
print("merged ->", OUT)
