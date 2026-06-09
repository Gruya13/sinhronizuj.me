import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"

def main():
    print("[1] Povezujem se na server preko SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(IP, port=PORT, username=USER, timeout=10)
        print("[USPEH] Povezan!")
        
        # --- KORAK 1: SSH Hardening (Onemogućavanje lozinke) ---
        print("\n[+] Izvrsavam SSH Hardening (onemogucavanje lozinke)...")
        ssh_cmds = [
            # Bekapujemo sshd_config za svaki slucaj
            "cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak",
            # Menjamo PasswordAuthentication u no
            "sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/g' /etc/ssh/sshd_config",
            "sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/g' /etc/ssh/sshd_config",
            "sed -i 's/#PasswordAuthentication no/PasswordAuthentication no/g' /etc/ssh/sshd_config",
            # Iskljucujemo ostale interaktivne autentifikacije lozinkom
            "sed -i 's/#KbdInteractiveAuthentication yes/KbdInteractiveAuthentication no/g' /etc/ssh/sshd_config",
            "sed -i 's/KbdInteractiveAuthentication yes/KbdInteractiveAuthentication no/g' /etc/ssh/sshd_config",
            # Restartujemo SSH servis da primenimo izmene
            "systemctl restart ssh || systemctl restart sshd"
        ]
        for cmd in ssh_cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
        print("[USPEH] SSH je konfigurisan da odbija lozinke. Pristup je moguc iskljucivo preko kljuca.")

        # --- KORAK 2: Instalacija i konfiguracija Fail2Ban ---
        print("\n[+] Instaliram i pokrecem fail2ban...")
        fail2ban_cmds = [
            "apt-get update",
            "apt-get install -y fail2ban",
            "systemctl restart fail2ban",
            "systemctl enable fail2ban"
        ]
        for cmd in fail2ban_cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
            
        stdin, stdout, stderr = ssh.exec_command("systemctl is-active fail2ban")
        status = stdout.read().decode().strip()
        print(f"[USPEH] Fail2Ban je instaliran i status je: {status}")

        # --- KORAK 3: Instalacija Certbot-a ---
        print("\n[+] Instaliram Certbot i Nginx plugin za SSL...")
        certbot_cmds = [
            "apt-get install -y certbot python3-certbot-nginx"
        ]
        for cmd in certbot_cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
        print("[USPEH] Certbot je instaliran. Server je spreman za HTTPS.")

        # --- KORAK 4: Povlačenje najnovijeg koda (Git Pull) i restart API-ja ---
        print("\n[+] Povlacim najnovije izmene sa Git-a i restartujem API na serveru...")
        git_cmds = [
            "cd /opt/sinhronizuj.me && git pull origin development",
            "cd /opt/sinhronizuj.me && docker compose -f infra/hetzner/docker-compose.prod.yml restart api"
        ]
        for cmd in git_cmds:
            print(f"Izvrsavam: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            if out: print("OUT:", out)
            if err: print("ERR:", err)
        print("[USPEH] Kod je azuriran i FastAPI server je restartovan sa novim trajanjem presigned URL-ova.")

    except Exception as e:
        print(f"[GREŠKA] Hardening nije uspeo: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
