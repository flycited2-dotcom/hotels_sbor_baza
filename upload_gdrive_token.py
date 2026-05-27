#!/usr/bin/env python3
"""Upload token.json to the production server.

Run after setup_gdrive_auth.py to deploy the OAuth2 token.
Edit SERVER / USER below if needed.
"""
import os
import sys

SERVER = "31.129.102.226"
USER = "root"
REMOTE_PATH = "/home/crimea_parser/token.json"
LOCAL_TOKEN = "token.json"


def main() -> None:
    if not os.path.exists(LOCAL_TOKEN):
        print(f"ERROR: {LOCAL_TOKEN} not found. Run setup_gdrive_auth.py first.")
        sys.exit(1)

    try:
        import paramiko
    except ImportError:
        print("paramiko not installed — using scp instead")
        os.system(f'scp {LOCAL_TOKEN} {USER}@{SERVER}:{REMOTE_PATH}')
        return

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    password = os.getenv("SSH_PASS") or input(f"Password for {USER}@{SERVER}: ")
    ssh.connect(SERVER, username=USER, password=password, timeout=30)

    sftp = ssh.open_sftp()
    sftp.put(LOCAL_TOKEN, REMOTE_PATH)
    sftp.chmod(REMOTE_PATH, 0o600)
    sftp.close()
    ssh.close()

    print(f"✅ token.json uploaded to {USER}@{SERVER}:{REMOTE_PATH}")
    print()
    print("Test with:")
    print("  ssh root@<server> python3 /home/crimea_parser/test_gdrive.py")


if __name__ == "__main__":
    main()
