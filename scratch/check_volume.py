import modal
import os

app = modal.App("check-volume")
vol = modal.NetworkFileSystem.from_name("sinhronizuj-models")

@app.function(network_file_systems={"/models": vol})
def check():
    for f in os.listdir("/models/qwen-vl-7b"):
        path = os.path.join("/models/qwen-vl-7b", f)
        print(f"{f}: {os.path.getsize(path)}")

@app.local_entrypoint()
def main():
    check.remote()
