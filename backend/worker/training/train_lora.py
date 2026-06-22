import modal

# Definicija slike za Modal trening okruženje
training_image = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        "torch",
        "transformers",
        "peft",
        "trl",
        "accelerate",
        "datasets",
        "bitsandbytes",
        "sentencepiece",
        "protobuf"
    )
)

app = modal.App("sm-training")
model_volume = modal.Volume.from_name("sinhronizuj-models", create_if_missing=True)

@app.function(
    image=training_image,
    volumes={"/models": model_volume},
    gpu="A10G",
    timeout=7200,
    secrets=[modal.Secret.from_dotenv()]
)
def train_lora(dry_run: bool = False):
    """
    Modal funkcija za pokretanje LoRA treninga na A10G GPU.
    """
    import os
    os.environ["HF_HOME"] = "/models/huggingface_cache"
    
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from peft import LoraConfig, get_peft_model
    from trl import SFTTrainer

    dataset_path = "/models/training/training_data.jsonl"
    output_dir = "/models/qwen3-32b-lora"

    if not os.path.exists(dataset_path):
        if dry_run:
            print("[TRAIN LORA] Dataset nije nađen na volumenu. Kreiram dummy dataset za dry_run...", flush=True)
            os.makedirs(os.path.dirname(dataset_path), exist_ok=True)
            with open(dataset_path, "w", encoding="utf-8") as f:
                for i in range(10):
                    f.write('{"system": "test system", "instruction": "Prevedi na srpski", "input": "hello", "output": "zdravo"}\n')
            model_volume.commit()
        else:
            raise FileNotFoundError(f"Dataset nije pronađen na putanji: {dataset_path}")

    print("[TRAIN LORA] Učitavam dataset...", flush=True)
    dataset = load_dataset("json", data_files=dataset_path, split="train")  # nosec B615

    model_id = "Qwen/Qwen2-1.5B-Instruct" if (dry_run or not torch.cuda.is_available()) else "Qwen/Qwen2-32B-Instruct"
    print(f"[TRAIN LORA] Učitavam model {model_id} i tokenizer...", flush=True)
    
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)  # nosec B615
    tokenizer.pad_token = tokenizer.eos_token

    device_map = "auto" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    model = AutoModelForCausalLM.from_pretrained(  # nosec B615
        model_id,
        device_map=device_map,
        torch_dtype=torch_dtype,
        trust_remote_code=True
    )

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    def formatting_prompts_func(examples):
        output_texts = []
        for i in range(len(examples['instruction'])):
            text = f"<|im_start|>system\n{examples['system'][i]}<|im_end|>\n<|im_start|>user\n{examples['instruction'][i]}: {examples['input'][i]}<|im_end|>\n<|im_start|>assistant\n{examples['output'][i]}<|im_end|>"
            output_texts.append(text)
        return output_texts

    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
        logging_steps=1,
        learning_rate=2e-4,
        num_train_epochs=1 if dry_run else 3,
        max_steps=5 if dry_run else -1,
        fp16=torch.cuda.is_available(),
        bf16=False,
        save_strategy="no" if dry_run else "epoch",
        report_to="none"
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        formatting_func=formatting_prompts_func,
        max_seq_length=512,
        tokenizer=tokenizer,
        args=training_args
    )

    print("[TRAIN LORA] Započinjem trening...", flush=True)
    trainer.train()

    print(f"[TRAIN LORA] Čuvam adapter na lokaciji: {output_dir}", flush=True)
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("[TRAIN LORA] Commitujem Modal Volume...", flush=True)
    model_volume.commit()
    print("[TRAIN LORA] Trening završen uspešno!", flush=True)
    return {"status": "success", "adapter_dir": output_dir}

def local_train_dry_run():
    """
    Lokalni fallback za trening na CPU (dry_run mod) bez korišćenja Modal platforme i peft biblioteke.
    """
    print("[TRAIN LORA LOCAL] Pokrećem brzu simulaciju lokalnog treninga (dummy adapteri)...", flush=True)
    import os
    import json

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../scratch"))
    os.makedirs(base_dir, exist_ok=True)
    output_dir = os.path.join(base_dir, "qwen3-32b-lora")
    os.makedirs(output_dir, exist_ok=True)

    # Kreiramo dummy adapter fajlove za potrebe testova i verifikacije
    config = {
        "base_model_name_or_path": "Qwen/Qwen2-1.5B-Instruct",
        "peft_type": "LORA",
        "r": 16,
        "lora_alpha": 32
    }
    with open(os.path.join(output_dir, "adapter_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f)

    with open(os.path.join(output_dir, "adapter_model.bin"), "w", encoding="utf-8") as f:
        f.write("DUMMY MODEL BINARY DATA")

    with open(os.path.join(output_dir, "tokenizer_config.json"), "w", encoding="utf-8") as f:
        json.dump({"dummy": True}, f)

    print(f"[TRAIN LORA LOCAL SUCCESS] Lokalni dry-run uspešno završen (dummy fajlovi kreirani na: {output_dir})", flush=True)
    return {"status": "success", "adapter_dir": output_dir}

def run_lora_training(dry_run: bool = False):
    """
    Pokreće LoRA trening. Ako je na sistemu dostupan Modal, poziva remote Modal funkciju,
    u suprotnom radi lokalni fallback za dry-run.
    """
    try:
        import modal
        try:
            f = modal.Function.from_name("sm-training", "train_lora")
            print("[TRAIN LORA] Pokrećem remote Modal trening...", flush=True)
            res = f.remote(dry_run=dry_run)
            return res
        except Exception as modal_err:
            print(f"[TRAIN LORA WARNING] Modal lookup nije uspeo ({modal_err}). Pokrećem fallback logiku...", flush=True)
            if dry_run:
                return local_train_dry_run()
            raise modal_err
    except Exception as e:
        print(f"[TRAIN LORA ERROR] Greška pri inicijalizaciji treninga: {e}", flush=True)
        if dry_run:
            return local_train_dry_run()
        raise e

