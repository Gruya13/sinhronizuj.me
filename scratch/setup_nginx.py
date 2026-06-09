import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"

nginx_conf = """server {
    listen 80;
    server_name _;

    # FastAPI API proksiranje
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Povecana granica za upload fajlova (npr. za velike video zapise)
        client_max_body_size 500M;
    }
}
"""

def main():
    print("[1] Povezujem se na server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(IP, port=PORT, username=USER, timeout=10)
        print("[USPEH] Povezan!")
        
        # 1. Instalacija Nginx-a
        print("\n[+] Instaliram Nginx...")
        stdin, stdout, stderr = ssh.exec_command("apt-get update && apt-get install -y nginx")
        stdout.read()
        print("[USPEH] Nginx instaliran.")
        
        # 2. Upisivanje Nginx konfiguracije
        print("\n[+] Kreiram Nginx konfiguraciju...")
        sftp = ssh.open_sftp()
        conf_path = "/etc/nginx/sites-available/sinhronizuj.me"
        with sftp.file(conf_path, "w") as f:
            f.write(nginx_conf)
        sftp.close()
        
        # Omogucavanje konfiguracije i brisanje default-a
        nginx_cmds = [
            "rm -f /etc/nginx/sites-enabled/default",
            "ln -sf /etc/nginx/sites-available/sinhronizuj.me /etc/nginx/sites-enabled/",
            "systemctl restart nginx",
            "systemctl enable nginx"
        ]
        for cmd in nginx_cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
        print("[USPEH] Nginx konfigurisan i pokrenut na portu 80.")
        
        # 3. Konfiguracija UFW Firewall-a
        print("\n[+] Konfigurisem UFW Firewall...")
        ufw_cmds = [
            "ufw allow 22/tcp",
            "ufw allow 80/tcp",
            "ufw allow 443/tcp",
            "ufw allow 9000/tcp",
            "ufw allow 9001/tcp",
            "ufw --force enable"
        ]
        for cmd in ufw_cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
            
        stdin, stdout, stderr = ssh.exec_command("ufw status")
        print("UFW Status:\n", stdout.read().decode().strip())
        print("[USPEH] UFW konfigurisan.")
        
    except Exception as e:
        print(f"[GREŠKA] Konfiguracija Nginx-a nije uspela: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
