import requests
import json

API_TOKEN = "cfat_1wpAR1mybvT6T6f1WwMwscYmZ7ZGq9WglMrK9n0Qfd1e247f"
ZONE_ID = "860ad2da09458663a1769e868e9a8894"
IP_ADDRESS = "178.104.214.78"

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
    print(f"Pronadjeno ukupno {len(records)} DNS zapisa.")
    
    for r in records:
        r_id = r.get("id")
        r_type = r.get("type")
        r_name = r.get("name")
        r_content = r.get("content")
        r_proxied = r.get("proxied")
        
        # Proveravamo A zapise koji pokazuju na nas server i nisu proxied
        if r_type == "A" and r_content == IP_ADDRESS:
            if not r_proxied:
                print(f"[+] Aktiviram proxy za zapis: {r_name} (ID: {r_id})...")
                patch_url = f"{url}/{r_id}"
                payload = {
                    "type": r_type,
                    "name": r_name,
                    "content": r_content,
                    "ttl": 1, # Auto TTL je obavezan kada je proxied=True
                    "proxied": True
                }
                patch_res = requests.patch(patch_url, headers=headers, json=payload)
                if patch_res.status_code == 200:
                    print(f"[USPEH] Proxy je aktiviran.")
                else:
                    print(f"[GREŠKA] Neuspesno aktiviranje: {patch_res.status_code}")
                    print(patch_res.text)
            else:
                print(f"[INFO] Zapis je vec proxied: {r_name}. Preskacem.")

if __name__ == "__main__":
    main()
