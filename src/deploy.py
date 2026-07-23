import os
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output"
DEPLOY_LOCK = Path("/tmp/daily_news_deploy.lock")


def check_disk(min_gb=1):
    import shutil
    total, used, free = shutil.disk_usage(Path(__file__).parent.parent)
    free_gb = free // (2**30)
    if free_gb < min_gb:
        raise OSError(f"Disco insuficiente: {free_gb}GB libres (min {min_gb}GB)")


def check_running_services(host):
    try:
        result = subprocess.run(
            ["ssh", host, "docker ps --format '{{.Names}}' 2>/dev/null; "
             "ss -tlnp | grep -E '80|443|8080'"],
            capture_output=True, text=True, timeout=10
        )
        print(f"  [INFO] Servicios en {host}: {result.stdout[:200]}")
    except Exception as e:
        print(f"  [WARN] No se pudieron listar servicios: {e}")


def deploy_github_safe(output_dir):
    try:
        subprocess.run(
            f"cd {output_dir} && git init && "
            f"git config user.email 'daily-news-bot@bot.local' && "
            f"git config user.name 'Daily News Bot' && "
            f"git add -A && git commit -m 'Auto-update: $(date -u)' && "
            f"git remote add origin git@github.com:mcasrom/daily_readings.git && "
            f"git branch -M main && git push -f origin main",
            shell=True, check=True, capture_output=True, timeout=120,
        )
        print("  [OK] Deploy GitHub completado")
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode()[:300] if e.stderr else ""
        if "Repository not found" in stderr:
            print("  [WARN] Repo GitHub no encontrado. Crea mcasrom/daily_readings primero")
        else:
            print(f"  [WARN] Deploy GitHub: {stderr}")
        return False
    except subprocess.TimeoutExpired:
        print("  [WARN] Deploy GitHub: timeout")
        return False


def deploy_server_safe(host, remote_path):
    output_dir = OUTPUT_DIR
    if not output_dir.exists():
        print("  [WARN] No hay output para deployar")
        return False

    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", host,
             f"mkdir -p {remote_path} && df -h {remote_path} | tail -1"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"  [WARN] No se puede acceder a {host}:{remote_path}")
            return False

        print(f"  [INFO] Server OK: {result.stdout.strip()}")

        result = subprocess.run(
            ["rsync", "-avz", "--delete",
             "--exclude=.git",
             f"{output_dir}/", f"{host}:{remote_path}/"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print(f"  [OK] rsync a {host}:{remote_path} completado")
            return True
        else:
            print(f"  [WARN] rsync falló: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  [WARN] Timeout conectando a {host}")
        return False
    except Exception as e:
        print(f"  [WARN] Deploy server: {e}")
        return False


def verify_deploy(host, remote_path):
    try:
        result = subprocess.run(
            ["ssh", host, f"ls -la {remote_path}/index.html 2>/dev/null && wc -c {remote_path}/index.html"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"  [OK] Verificado: index.html en {host}")
            return True
        else:
            print(f"  [WARN] index.html no encontrado en {host}")
            return False
    except Exception as e:
        print(f"  [WARN] Verificación falló: {e}")
        return False


def deploy(mode="test", config=None):
    if mode == "test":
        print("  [TEST] Deploy simulado. Archivos listos en output/")
        return True

    if not config:
        return False

    try:
        check_disk(1)
    except OSError as e:
        print(f"  [ERROR] {e}")
        return False

    owner = config.get("server_host", "viaje")
    remote_path = config.get("server_path", "/var/www/daily_readings")

    print(f"  [INFO] Destino: {owner}:{remote_path}")

    check_running_services(owner)

    ok = True
    ok &= deploy_github_safe(OUTPUT_DIR)
    ok &= deploy_server_safe(owner, remote_path)
    ok &= verify_deploy(owner, remote_path)

    return ok
