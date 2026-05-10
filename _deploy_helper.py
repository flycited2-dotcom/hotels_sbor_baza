"""SSH deploy helper. Streams stdout/stderr in real time."""
import io
import sys
import paramiko
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = "212.116.115.150"
USER = "root"
PASS = "tRu741mAz"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30, auth_timeout=30, look_for_keys=False, allow_agent=False)
    return c

def run(c, cmd, timeout=60, get_pty=False):
    print(f"\n$ {cmd}", flush=True)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out, end="" if out.endswith("\n") else "\n", flush=True)
    if err:
        print("STDERR:", err, end="" if err.endswith("\n") else "\n", flush=True)
    print(f"[exit {code}]", flush=True)
    return code, out, err

def upload(c, local, remote):
    print(f"\nSCP {local} -> {remote}", flush=True)
    sftp = c.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    print("upload OK", flush=True)

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "deploy"
    c = connect()
    try:
        if action == "ping":
            run(c, "uname -a; lsb_release -a 2>/dev/null; whoami; pwd")
        elif action == "upload":
            upload(c, "crimea_parser.tar.gz", "/root/crimea_parser.tar.gz")
        elif action == "extract":
            run(c, "cd /root && rm -rf crimea_parser && tar -xzf crimea_parser.tar.gz && ls -la crimea_parser/")
        elif action == "deploy":
            run(c, "cd /root/crimea_parser && bash deploy.sh < <(echo n)", timeout=900, get_pty=True)
        elif action == "exec":
            cmd = sys.argv[2]
            t = int(sys.argv[3]) if len(sys.argv) > 3 else 120
            run(c, cmd, timeout=t, get_pty=True)
        else:
            print(f"unknown action: {action}")
    finally:
        c.close()

if __name__ == "__main__":
    main()
