import os
import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"
PASSWORD = "xdKdWjNJEKqxwCjnupEw"

def read_local_pub_keys():
    keys = []
    ssh_dir = os.path.expanduser("~/.ssh")
    for key_file in ["id_ed25519.pub", "id_rsa.pub"]:
        path = os.path.join(ssh_dir, key_file)
        if os.path.exists(path):
            with open(path, "r") as f:
                keys.append(f.read().strip())
    return keys

def main():
    print("[1] Ucitavam lokalne javne kljuceve...")
    pub_keys = read_local_pub_keys()
    if not pub_keys:
        print("[GREŠKA] Nisu pronadjeni lokalni javni kljucevi u ~/.ssh/")
        return
        
    print(f"[2] Povezujem se na {IP} preko SSH sa lozinkom...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(IP, port=PORT, username=USER, password=PASSWORD, timeout=10)
        print("[USPEH] Povezan!")
        
        # Proveravamo / kreiramo .ssh direktorijum na serveru
        print("[3] Kreiram ~/.ssh/ i dodajem kljuceve u authorized_keys...")
        stdin, stdout, stderr = ssh.exec_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh")
        stdout.read() # wait
        
        for key in pub_keys:
            # Dodajemo kljuc ako vec ne postoji
            cmd = f'grep -qF "{key}" ~/.ssh/authorized_keys 2>/dev/null || echo "{key}" >> ~/.ssh/authorized_keys'
            ssh.exec_command(cmd)
            
        stdin, stdout, stderr = ssh.exec_command("chmod 600 ~/.ssh/authorized_keys")
        stdout.read() # wait
        print("[USPEH] Javni kljucevi su dodati u authorized_keys na serveru.")
        
    except Exception as e:
        print(f"[GREŠKA] Povezivanje ili podesavanje nije uspelo: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
