import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
res = requests.get(url)
if res.status_code == 200:
    models = res.json().get("models", [])
    for m in models:
        print(m["name"], m["supportedGenerationMethods"])
else:
    print(res.status_code, res.text)
