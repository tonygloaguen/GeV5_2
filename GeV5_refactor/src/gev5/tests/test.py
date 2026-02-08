import subprocess

subprocess.run(["sudo", "pkill", "chromium"], check=True)
