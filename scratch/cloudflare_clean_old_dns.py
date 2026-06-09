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
        
        # Proveravamo A zapise za nas domen
        if r_type == "A" and r_name in [DOMAIN, f"api.{DOMAIN}", f"www.{DOMAIN}"]:
            if r_content != CORRECT_IP:
                print(f"[-] Brisem stari A zapis: {r_name} -> {r_content} (ID: {r_id})...")
                del_url = f"{url}/{r_id}"
                del_res = requests.delete(del_url, headers=headers)
                if del_res.status_code == 200:
                    print(f"[USPEH] Obrisano.")
                else:
                    print(f"[GREŠKA] Neuspesno brisanje: {del_res.status_code}")
                    print(del_res.text)
            else:
                print(f"[INFO] Zapis je ispravan: {r_name} -> {r_content}. Ostavljam.")

if __name__ == "__main__":
    main()
