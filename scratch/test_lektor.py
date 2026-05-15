import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("MODAL_LEKTOR_URL")
if not URL:
    print("GRESKA: MODAL_LEKTOR_URL nije pronadjen u .env fajlu!")
    exit(1)

print(f"Testiram Lektor radnika na: {URL}")

# Simulacija ulaza za lektora
test_input = "0|ENG: Check the articles of incorporation. | SRB: Proverite člankove u korporaciju.\n"

prompt = (
    "Ti si glavni lektor i korektor za srpski jezik (ekavica). Tvoj jedini zadatak je da pregledaš grubi prevod i ispraviš gramatiku, padeže, idiome i neprirodne izraze.\n\n"
    "PRAVILA ZA LEKTURU:\n"
    "1. Engleski tekst je dat samo kao kontekst. Tvoj izlaz mora biti SAMO korigovani SRPSKI tekst.\n"
    "2. Ispravi rogobatne prevode (npr. 'člankovi u korporaciju' prepravi u 'osnivački akti/dokumenta', a 'objavila zaposlenja' u 'objavila oglase za posao').\n"
    "3. Zadrži isti broj linija. Svaka linija mora početi sa ID| (npr. 0|Korigovani prevod).\n"
    "4. ZABRANJENO je objašnjavanje, vrati samo čiste korigovane redove.\n\n"
    f"TEKST ZA LEKTURU:\n{test_input}"
)

payload = {
    "model": "Qwen/Qwen2.5-32B-Instruct",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.2,
    "max_tokens": 2048
}

URL = f"{URL.rstrip('/')}/v1/chat/completions"

print("Saljem zahtev (ovo moze potrajati zbog Cold Start-a)...")
try:
    response = requests.post(URL, json=payload, timeout=600)
    if response.status_code == 200:
        print("USPEH!")
        print(f"Rezultat: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"GRESKA {response.status_code}: {response.text}")
except Exception as e:
    print(f"IZUZETAK: {e}")
