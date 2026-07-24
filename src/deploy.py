import os
import json
import subprocess
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def deploy(mode="test", config=None):
    if mode == "test":
        print("  [TEST] Deploy simulado. Archivos listos en output/")
        return True

    remote_path = config.get("server_path", "/var/www/daily_readings") if config else "/var/www/daily_readings"

    if not OUTPUT_DIR.exists():
        print("  [WARN] No hay output para deployar")
        return False

    try:
        subprocess.run(["sudo", "cp", "-r", str(OUTPUT_DIR) + "/.", remote_path], check=True, timeout=30)
        subprocess.run(["sudo", "chown", "-R", "deploy:deploy", remote_path], check=True, timeout=10)
        print(f"  [OK] Copiado a {remote_path}")
        return True
    except Exception as e:
        print(f"  [WARN] Deploy: {e}")
        return False
