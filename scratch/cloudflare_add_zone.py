import requests

API_TOKEN = "cfat_onOLWH5doRCOBgE1H1HDoD0VkE5olnR41vGrSMvy20c687e6"
ACCOUNT_ID = "95dd4d541ae833073f744165d7485f2b"
DOMAIN = "sinhronizuj.me"

def main():
    url = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": DOMAIN,
        "account": {"id": ACCOUNT_ID},
        "jump_start_dns": True
    }
    
    print(f"[+] Dodajem domen {DOMAIN} na Cloudflare...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200 or response.status_code == 201:
        data = response.json()
        result = data.get("result", {})
        zone_id = result.get("id")
        name_servers = result.get("name_servers", [])
        status = result.get("status")
        print(f"[USPEH] Zone ID: {zone_id}")
        print(f"Status: {status}")
        print("Nameserveri koje treba postaviti na Loopia:")
        for ns in name_servers:
            print(f" - {ns}")
    else:
        print(f"[GREŠKA] Status: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()
