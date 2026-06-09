import requests

API_TOKEN = "cfat_1wpAR1mybvT6T6f1WwMwscYmZ7ZGq9WglMrK9n0Qfd1e247f"
ZONE_ID = "860ad2da09458663a1769e868e9a8894"

def main():
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        records = response.json().get("result", [])
        print("Trenutni DNS zapisi na Cloudflare-u:")
        for r in records:
            print(f" - Name: {r.get('name')}, Type: {r.get('type')}, Content: {r.get('content')}, Proxied: {r.get('proxied')}")
    else:
        print("Greška:", response.text)

if __name__ == "__main__":
    main()
