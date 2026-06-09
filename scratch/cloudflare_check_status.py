import requests
import json

API_TOKEN = "cfat_1wpAR1mybvT6T6f1WwMwscYmZ7ZGq9WglMrK9n0Qfd1e247f"
ZONE_ID = "860ad2da09458663a1769e868e9a8894"

def main():
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("[+] Preuzimam sve DNS zapise sa Cloudflare-a...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"[GREŠKA] Neuspesno preuzimanje zapisa: {response.status_code}")
        print(response.text)
        return
        
    records = response.json().get("result", [])
    print(f"Pronadjeno ukupno {len(records)} DNS zapisa:")
    for r in records:
        print(f"- {r.get('name')} ({r.get('type')}) -> {r.get('content')} (Proxied: {r.get('proxied')})")

if __name__ == "__main__":
    main()
