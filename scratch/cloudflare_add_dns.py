import requests

API_TOKEN = "cfat_1wpAR1mybvT6T6f1WwMwscYmZ7ZGq9WglMrK9n0Qfd1e247f"
ZONE_ID = "860ad2da09458663a1769e868e9a8894"
IP_ADDRESS = "116.202.103.35"
DOMAIN = "sinhronizuj.me"

dns_records = [
    {"type": "A", "name": "@", "content": IP_ADDRESS, "proxied": False},
    {"type": "A", "name": "api", "content": IP_ADDRESS, "proxied": False},
    {"type": "A", "name": "www", "content": IP_ADDRESS, "proxied": False}
]

def main():
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"[+] Dodajem DNS zapise na Cloudflare za zonu {ZONE_ID}...")
    
    # Prvo proveravamo da li zapisi vec postoje da ne bismo pravili duplikate
    try:
        get_response = requests.get(url, headers=headers)
        existing_records = []
        if get_response.status_code == 200:
            existing_records = get_response.json().get("result", [])
    except Exception as e:
        print(f"[UPOZORENJE] Nije uspela provera postojecih zapisa: {e}")
        existing_records = []
        
    for record in dns_records:
        name_full = DOMAIN if record["name"] == "@" else f"{record['name']}.{DOMAIN}"
        
        # Provera duplikata
        is_duplicate = False
        for ext in existing_records:
            if ext.get("name") == name_full and ext.get("type") == record["type"] and ext.get("content") == record["content"]:
                print(f"[INFO] Zapis {name_full} ({record['type']} -> {record['content']}) vec postoji. Preskacem.")
                is_duplicate = True
                break
                
        if is_duplicate:
            continue
            
        payload = {
            "type": record["type"],
            "name": record["name"],
            "content": record["content"],
            "ttl": 1,  # Auto TTL
            "proxied": record["proxied"]
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200 or response.status_code == 201:
            print(f"[USPEH] Dodat zapis: {name_full} A -> {IP_ADDRESS}")
        else:
            print(f"[GREŠKA] Neuspesno dodavanje za {name_full}: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    main()
