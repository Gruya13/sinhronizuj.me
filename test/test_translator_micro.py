import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

MODAL_TRANSLATOR_URL = os.getenv("MODAL_TRANSLATOR_URL")
MODAL_LEKTOR_URL = os.getenv("MODAL_LEKTOR_URL")

print(f"MODAL_TRANSLATOR_URL: {MODAL_TRANSLATOR_URL}")
print(f"MODAL_LEKTOR_URL: {MODAL_LEKTOR_URL}")

def test_translator():
    print("\n--- Testiranje Modal Translatora (Qwen2-VL) ---")
    if not MODAL_TRANSLATOR_URL:
        print("Greška: MODAL_TRANSLATOR_URL nije definisan u .env")
        return
        
    url = f"{MODAL_TRANSLATOR_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": "qwen-vl",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Ti si profesionalni prevodilac. Prevedi sledeću liniju na srpski (ekavica):\n0|Hello, how are you today?"}
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 100
    }
    
    print(f"Šaljem zahtev na {url}...")
    start_time = time.time() if 'time' in globals() else 0
    import time
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=120)
        print(f"HTTP Status: {response.status_code}")
        print(f"Vreme izvršavanja: {time.time() - start_time:.2f}s")
        if response.status_code == 200:
            print("Odgovor:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            return True
        else:
            print(f"Greška: {response.text}")
            return False
    except Exception as e:
        print(f"Greška pri slanju zahteva: {e}")
        return False

def test_lektor():
    print("\n--- Testiranje Modal Lektora (Qwen 2.5 32B) ---")
    if not MODAL_LEKTOR_URL:
        print("Greška: MODAL_LEKTOR_URL nije definisan u .env")
        return
        
    url = f"{MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": "qwen-lektor",
        "messages": [
            {
                "role": "user",
                "content": "Ti si glavni lektor za srpski jezik. Ispravi sledeću rečenicu:\n0|ENG: I love eating apples. | SRB: Ja voleti da jedem jabuka."
            }
        ],
        "temperature": 0.2,
        "max_tokens": 100
    }
    
    print(f"Šaljem zahtev na {url}...")
    import time
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=120)
        print(f"HTTP Status: {response.status_code}")
        print(f"Vreme izvršavanja: {time.time() - start_time:.2f}s")
        if response.status_code == 200:
            print("Odgovor:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            return True
        else:
            print(f"Greška: {response.text}")
            return False
    except Exception as e:
        print(f"Greška pri slanju zahteva: {e}")
        return False

if __name__ == "__main__":
    t_ok = test_translator()
    l_ok = test_lektor()
    print(f"\nRezultat testova: Translator={t_ok}, Lektor={l_ok}")
