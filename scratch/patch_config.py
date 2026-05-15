import modal
import json
import os

VOLUME_PATH = "/models"
models_volume = modal.NetworkFileSystem.from_name("sinhronizuj-models", create_if_missing=True)

app = modal.App("patch-config")

@app.function(network_file_systems={VOLUME_PATH: models_volume})
def patch():
    config_path = f"{VOLUME_PATH}/qwen-vl-7b-awq/config.json"
    if not os.path.exists(config_path):
        print(f"Config ne postoji na putanji: {config_path}")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    if "rope_scaling" in config and isinstance(config["rope_scaling"], dict):
        rs = config["rope_scaling"]
        if "type" in rs and rs["type"] == "mrope":
            print("Menjam 'type': 'mrope' u 'rope_type': 'mrope' radi kompatibilnosti sa vLLM 0.6.6+")
            rs["rope_type"] = "mrope"
            del rs["type"]
            
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            print("Config uspešno patch-ovan.")
        else:
            print("Nije pronađen legacy 'type': 'mrope' u rope_scaling sekciji.")
    else:
        print("rope_scaling nije pronađen u configu.")

if __name__ == "__main__":
    with app.run():
        patch.remote()
