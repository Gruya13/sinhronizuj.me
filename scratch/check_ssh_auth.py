import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"
PASSWORD = "xdKdWjNJEKqxwCjnupEw"

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(IP, port=PORT, username=USER, password=PASSWORD, timeout=10)
        
        # 1. Provera permisija
        print("--- Permisije ---")
        cmds = [
            "ls -ld ~",
            "ls -ld ~/.ssh",
            "ls -l ~/.ssh/authorized_keys",
            "cat ~/.ssh/authorized_keys | wc -l"
        ]
        for cmd in cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            print(f"$ {cmd}")
            if out: print("OUT:", out)
            if err: print("ERR:", err)
            
        # 2. Provera sshd_config
        print("\n--- sshd_config ---")
        for cmd in ["grep -i 'PubkeyAuthentication' /etc/ssh/sshd_config", "grep -i 'AuthorizedKeysFile' /etc/ssh/sshd_config"]:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            print(f"$ {cmd}")
            if out: print("OUT:", out)
            if err: print("ERR:", err)
        
        # 3. Pogledajmo auth.log na kratko ako postoji (npr. tail)
        print("\n--- auth.log tail ---")
        stdin, stdout, stderr = ssh.exec_command("tail -n 10 /var/log/auth.log 2>/dev/null || tail -n 10 /var/log/secure")
        print("OUT:", stdout.read().decode().strip())
        print("ERR:", stderr.read().decode().strip())
        
    except Exception as e:
        print("Greška:", e)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
