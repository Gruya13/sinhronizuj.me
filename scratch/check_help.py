import modal
import subprocess

app = modal.App("check-help")
image = modal.Image.debian_slim(python_version="3.11").apt_install("git").run_commands(
    "git clone --branch v1.5.1 https://github.com/fishaudio/fish-speech.git /opt/fish-speech",
    "cd /opt/fish-speech && pip install -e ."
)

@app.function(image=image)
def test_help():
    import glob
    llama_script = next(glob.iglob(f"/opt/fish-speech/**/text2semantic/inference.py", recursive=True), None)
    print("Llama script:", llama_script)
    res = subprocess.run(["python3", llama_script, "--help"], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
