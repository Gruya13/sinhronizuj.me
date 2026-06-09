import os
import time
import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"

def read_local_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return None

def main():
    print("[1] Povezujem se na server preko SSH pomocu kljuca...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(IP, port=PORT, username=USER, timeout=10)
        print("[USPEH] Povezan!")
        
        # --- KORAK 1: Podešavanje Swap-a (4 GB) ---
        print("\n[+] Proveravam Swap...")
        stdin, stdout, stderr = ssh.exec_command("swapon --show")
        swap_out = stdout.read().decode().strip()
        if swap_out:
            print(f"Swap vec postoji:\n{swap_out}")
        else:
            print("Swap ne postoji. Kreiram 4 GB swap fajl...")
            swap_cmds = [
                "fallocate -l 4G /swapfile",
                "chmod 600 /swapfile",
                "mkswap /swapfile",
                "swapon /swapfile",
                "echo '/swapfile none swap sw 0 0' >> /etc/fstab"
            ]
            for cmd in swap_cmds:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.read()
            print("[USPEH] Swap od 4 GB je kreiran i aktiviran.")

        # --- KORAK 2: Prenos lokalnih SSH ključeva za GitHub ---
        print("\n[+] Prenosim lokalne SSH kljuceve na server radi Git pristupa...")
        ssh_dir = os.path.expanduser("~/.ssh")
        for key_file in ["id_ed25519", "id_ed25519.pub", "id_rsa", "id_rsa.pub"]:
            local_path = os.path.join(ssh_dir, key_file)
            content = read_local_file(local_path)
            if content:
                print(f"Prenosim {key_file}...")
                # Upisujemo direktno na server
                sftp = ssh.open_sftp()
                remote_path = f"/root/.ssh/{key_file}"
                with sftp.file(remote_path, 'w') as f:
                    f.write(content)
                sftp.chmod(remote_path, 0o600 if not key_file.endswith(".pub") else 0o644)
                sftp.close()
        
        # Dodavanje github.com u known_hosts na serveru
        ssh.exec_command("ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts")
        print("[USPEH] SSH kljucevi preneti i GitHub host je dodat u known_hosts.")

        # --- KORAK 3: Instalacija Dockera i Docker Compose ---
        print("\n[+] Proveravam da li je Docker instaliran...")
        stdin, stdout, stderr = ssh.exec_command("which docker")
        docker_installed = stdout.read().decode().strip()
        
        if docker_installed:
            print("Docker je vec instaliran.")
        else:
            print("Docker nije instaliran. Započinjem instalaciju...")
            docker_install_cmds = [
                "apt-get update",
                "apt-get install -y ca-certificates curl gnupg lsb-release",
                "curl -fsSL https://get.docker.com -o get-docker.sh",
                "sh get-docker.sh",
                "apt-get install -y docker-compose-plugin git"
            ]
            for cmd in docker_install_cmds:
                print(f"Izvrsavam: {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.read() # Cekamo zavrsetak
            print("[USPEH] Docker i Docker Compose su instalirani.")

        # --- KORAK 4: Kloniranje repozitorijuma ---
        print("\n[+] Kloniram repozitorijum sinhronizuj.me...")
        # Proveravamo da li folder vec postoji
        stdin, stdout, stderr = ssh.exec_command("ls -d /opt/sinhronizuj.me 2>/dev/null")
        repo_exists = stdout.read().decode().strip()
        
        if repo_exists:
            print("Repozitorijum vec postoji u /opt/sinhronizuj.me. Povlacim najnovije izmene...")
            git_cmds = [
                "cd /opt/sinhronizuj.me && git fetch --all",
                "cd /opt/sinhronizuj.me && git checkout development",
                "cd /opt/sinhronizuj.me && git pull origin development"
            ]
        else:
            git_cmds = [
                "mkdir -p /opt",
                "cd /opt && git clone -b development git@github.com:Gruya13/sinhronizuj.me.git"
            ]
            
        for cmd in git_cmds:
            print(f"Izvrsavam: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            if out: print("OUT:", out)
            if err: print("ERR:", err)
            
        # --- KORAK 5: Kopiranje .env fajla ---
        print("\n[+] Kopiram lokalni .env na server...")
        local_env = read_local_file("/home/gruya/Projektri/sinhronizuj.me/.env")
        if local_env:
            sftp = ssh.open_sftp()
            with sftp.file("/opt/sinhronizuj.me/.env", "w") as f:
                f.write(local_env)
            sftp.chmod("/opt/sinhronizuj.me/.env", 0o600)
            sftp.close()
            print("[USPEH] .env kopiran.")
        else:
            print("[UPOZORENJE] Lokalni .env nije pronadjen!")

        print("\n[ZAVRŠENO] Osnovno podesavanje servera je kompletirano.")
        print("Sada je server spreman za pokretanje docker compose staka.")
        
    except Exception as e:
        print(f"[GREŠKA] Konfiguracija nije uspela: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
