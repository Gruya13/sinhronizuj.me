import xmlrpc.client

USERNAME = "sinhronizuj.me"
PASSWORD = "f2puWGanQsab"
API_URL = "https://api.loopia.se/RPCSERV"
DOMAIN = "sinhronizuj.me"

def main():
    print(f"[+] Povezujem se na Loopia API za domen {DOMAIN}...")
    client = xmlrpc.client.ServerProxy(API_URL)
    
    try:
        # getDomain metoda
        domain_info = client.getDomain(USERNAME, PASSWORD, DOMAIN)
        print("[USPEH] Uspesno povezan na Loopia API!")
        print("Podaci o domenu:")
        print(domain_info)
    except Exception as e:
        print(f"[GREŠKA] Loopia API poziv nije uspeo: {e}")
        print("Napomena: Proverite da li je LoopiaAPI omogucen u podesavanjima vaseg naloga na Loopia portalu.")

if __name__ == "__main__":
    main()
