import os
import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"

passwords = ["E89120d9dfeb@", "Eddfeb@", "xdKdWjNJEKqxwCjnupEw"]

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
    pub_keys = read_local_pub_keys()
    if not pub_keys:
        print("[GREŠKA] Nisu pronadjeni lokalni javni kljucevi u ~/.ssh/")
        return

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connected = False
    working_password = None
    
    for pwd in passwords:
        print(f"[TEST] Pokusavam povezivanje sa lozinkom: {pwd} ...")
        try:
            ssh.connect(IP, port=PORT, username=USER, password=pwd, timeout=5)
            print(f"[USPEH] Uspesno povezan sa lozinkom: {pwd}")
            connected = True
            working_password = pwd
            break
        except Exception as e:
            print(f"[NEUSPEH] Greška: {e}")
            
    if not connected:
        print("[GREŠKA] Nijedna lozinka ne radi.")
        return
        
    try:
        # Dodavanje kljuceva ponovo i sredjivanje permisija
        print("[+] Kreiram ~/.ssh/ i dodajem authorized_keys...")
        stdin, stdout, stderr = ssh.exec_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh")
        stdout.read()
        
        # Praznimo authorized_keys da budemo sigurni, pa dodajemo
        ssh.exec_command("echo '' > ~/.ssh/authorized_keys")
        
        for key in pub_keys:
            cmd = f'echo "{key}" >> ~/.ssh/authorized_keys'
            ssh.exec_command(cmd)
            
        stdin, stdout, stderr = ssh.exec_command("chmod 600 ~/.ssh/authorized_keys")
        stdout.read()
        
        # Sredjivanje permisija za /root i /root/.ssh
        ssh.exec_command("chown -R root:root ~/.ssh")
        print("[+] Permisije i kljucevi su podeseni.")
        
        # Da vidimo da li sshd dopusta PubkeyAuthentication
        stdin, stdout, stderr = ssh.exec_command("grep -i 'PubkeyAuthentication' /etc/ssh/sshd_config")
        print("sshd Pubkey:", stdout.read().decode().strip())
        
    except Exception as e:
        print(f"[GREŠKA] Tokom konfiguracije: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
