import requests

API_TOKEN = "cfat_onOLWH5doRCOBgE1H1HDoD0VkE5olnR41vGrSMvy20c687e6"
DOMAIN = "sinhronizuj.me"

def main():
    url = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {
        "name": DOMAIN
    }
    
    print(f"[+] Proveravam da li je domen {DOMAIN} na Cloudflare...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        results = data.get("result", [])
        if results:
            result = results[0]
            zone_id = result.get("id")
            name_servers = result.get("name_servers", [])
            status = result.get("status")
            print(f"[USPEH] Domen je vec dodat na Cloudflare!")
            print(f"Zone ID: {zone_id}")
            print(f"Status: {status}")
            print("Nameserveri:")
            for ns in name_servers:
                print(f" - {ns}")
        else:
            print("[INFO] Domen nije pronadjen na Cloudflare nalogu sa ovim tokenom.")
    else:
        print(f"[GREŠKA] Status: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()
