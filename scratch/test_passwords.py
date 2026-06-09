import paramiko

IP = "116.202.103.35"
PORT = 22
USER = "root"

variations = [
    "E89120ddfeb@",
    "E89120dfeb@",
    "E89120Eddfeb@",
    "E89120d9ddfeb@",
    "E89120dddfeb@",
    "E89120d9dfeb@",
    "Eddfeb@",
    "E89120"
]

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    for pwd in variations:
        print(f"[TEST] Lozinka: {pwd} ...")
        try:
            ssh.connect(IP, port=PORT, username=USER, password=pwd, timeout=5)
            print(f"[USPEH]!!! Uspesno povezan sa lozinkom: {pwd}")
            ssh.close()
            return
        except Exception as e:
            print(f"[NEUSPEH]: {e}")

if __name__ == "__main__":
    main()
