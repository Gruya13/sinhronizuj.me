from transformers import AutoProcessor
processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct-AWQ", trust_remote_code=True)
print("image_token" in dir(processor))
print("image_token_id" in dir(processor))
print(dir(processor))
