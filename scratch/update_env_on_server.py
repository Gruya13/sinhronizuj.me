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
        
        # 1. Čitanje postojećeg .env fajla sa servera
        sftp = ssh.open_sftp()
        env_path = "/opt/sinhronizuj.me/.env"
        print(f"[2] Citam {env_path} sa servera...")
        with sftp.file(env_path, "r") as f:
            content = f.read().decode("utf-8")
        
        # 2. Zamena starih konfiguracija novim
        print("[3] Modifikujem konfiguraciju za novi server...")
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith("MINIO_ENDPOINT="):
                new_lines.append("MINIO_ENDPOINT=minio:9000")
            elif line.startswith("MINIO_PUBLIC_ENDPOINT="):
                new_lines.append(f"MINIO_PUBLIC_ENDPOINT=http://{IP}:9000")
            elif line.startswith("REDIS_URL="):
                new_lines.append("REDIS_URL=redis://:1GjlbjEfc1Z8Dus1lWEQsOegDK9iGYNP@redis:6379/0")
            elif line.startswith("DATABASE_URL="):
                new_lines.append("DATABASE_URL=postgresql://sinhronizuj_user:sinhronizuj_pass_2026@db:5432/sinhronizuj_me")
            else:
                new_lines.append(line)
                
        # Proveravamo da li nedostaje MINIO_PUBLIC_ENDPOINT
        if not any(l.startswith("MINIO_PUBLIC_ENDPOINT=") for l in new_lines):
            new_lines.append(f"MINIO_PUBLIC_ENDPOINT=http://{IP}:9000")
            
        new_content = "\n".join(new_lines) + "\n"
        
        # Upisivanje modifikovanog .env nazad
        with sftp.file(env_path, "w") as f:
            f.write(new_content)
        sftp.close()
        print("[USPEH] .env je uspesno azuriran na serveru.")
        
        # 3. Pokretanje Docker Compose staka
        print("\n[4] Pokrecem Docker Compose stack na serveru...")
        cmd = "cd /opt/sinhronizuj.me && docker compose -f infra/hetzner/docker-compose.prod.yml up -d --build"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        # Pratimo output uživo
        while not stdout.channel.exit_status_ready():
            if stdout.channel.recv_ready():
                print(stdout.channel.recv(1024).decode('utf-8', errors='ignore'), end="")
            if stderr.channel.recv_ready():
                print(stderr.channel.recv(1024).decode('utf-8', errors='ignore'), end="")
                
        # Poslednji ostatak ispisujemo
        print(stdout.read().decode('utf-8', errors='ignore'))
        print(stderr.read().decode('utf-8', errors='ignore'))
        
        exit_code = stdout.channel.recv_exit_status()
        if exit_code == 0:
            print("\n[USPEH] Produkcijski Docker Compose stak je uspesno podignut!")
        else:
            print(f"\n[GREŠKA] Pokretanje staka je fail-ovalo sa exit kodom: {exit_code}")
            
    except Exception as e:
        print(f"[GREŠKA] Doslo je do greske: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
