import requests

API_TOKEN = "cfat_1wpAR1mybvT6T6f1WwMwscYmZ7ZGq9WglMrK9n0Qfd1e247f"
ZONE_ID = "860ad2da09458663a1769e868e9a8894"
CORRECT_IP = "116.202.103.35"
DOMAIN = "sinhronizuj.me"

def main():
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("[+] Preuzimam sve DNS zapise sa Cloudflare-a...")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[GREŠKA] Neuspesno preuzimanje: {response.status_code}")
        return
        
    records = response.json().get("result", [])
    
    for r in records:
        r_id = r.get("id")
        r_type = r.get("type")
        r_name = r.get("name")
        r_content = r.get("content")
        
        # Brisemo sve wildcard A zapise koji ne pokazuju na ispravan IP
        if r_type == "A" and r_name == f"*.{DOMAIN}":
            if r_content != CORRECT_IP:
                print(f"[-] Brisem stari wildcard zapis: {r_name} -> {r_content} (ID: {r_id})...")
                del_res = requests.delete(f"{url}/{r_id}", headers=headers)
                if del_res.status_code == 200:
                    print("[USPEH] Obrisano.")
                else:
                    print("[GREŠKA] Neuspesno brisanje.")
                    
    # Dodajemo novi ispravan wildcard
    print(f"[+] Dodajem novi wildcard A zapis: *.{DOMAIN} -> {CORRECT_IP}...")
    payload = {
        "type": "A",
        "name": "*",
        "content": CORRECT_IP,
        "ttl": 1,
        "proxied": False
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200 or response.status_code == 201:
        print("[USPEH] Novi wildcard dodat.")
    else:
        print(f"[GREŠKA] Neuspesno dodavanje wildcard-a: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()
