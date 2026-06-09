import requests
import json

API_TOKEN = "cfat_1wpAR1mybvT6T6f1WwMwscYmZ7ZGq9WglMrK9n0Qfd1e247f"
ZONE_ID = "860ad2da09458663a1769e868e9a8894"
OLD_IP = "116.202.103.35"
NEW_IP = "178.104.214.78"

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
        
        # Proveravamo A zapise koji pokazuju na stari server
        if r_type == "A" and r_content == OLD_IP:
            print(f"[+] Azuriram zapis: {r_name} (Stara IP: {OLD_IP} -> Nova IP: {NEW_IP})...")
            patch_url = f"{url}/{r_id}"
            payload = {
                "type": r_type,
                "name": r_name,
                "content": NEW_IP,
                "ttl": 1, # Auto TTL
                "proxied": False # Iskljucujemo proxy privremeno radi Certbota
            }
            patch_res = requests.patch(patch_url, headers=headers, json=payload)
            if patch_res.status_code == 200:
                print(f"[USPEH] Zapis je azuriran i prebacen na DNS-only.")
            else:
                print(f"[GREŠKA] Neuspesno azuriranje: {patch_res.status_code}")
                print(patch_res.text)

if __name__ == "__main__":
    main()
