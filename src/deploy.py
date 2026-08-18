import subprocess
import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output"
SITE = "https://news.viajeinteligencia.com"


def generate_sitemap():
    today = datetime.date.today().isoformat()
    urls = []
    for f in sorted(OUTPUT_DIR.glob("*_day_briefing.html")):
        urls.append(f"{SITE}/{f.name}")
    for name in ("clusters.html", "portada.html"):
        if (OUTPUT_DIR / name).exists():
            urls.append(f"{SITE}/{name}")
    if (OUTPUT_DIR / "index.html").exists():
        urls.insert(0, f"{SITE}/")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod><priority>0.7</priority></url>")
    lines.append("</urlset>")
    (OUTPUT_DIR / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [OK] Sitemap news: {len(urls)} urls")


def deploy(mode="test", config=None):
    if mode == "test":
        print("  [TEST] Deploy simulado")
        return True
    remote_path = "/var/www/daily_readings" if not config else config.get("server_path", "/var/www/daily_readings")
    if not OUTPUT_DIR.exists():
        print("  [WARN] No hay output")
        return False
    generate_sitemap()
    try:
        subprocess.run(["sudo", "rsync", "-avz", str(OUTPUT_DIR) + "/", remote_path + "/"], check=True, timeout=60)
        subprocess.run(["sudo", "chown", "-R", "deploy:deploy", remote_path], check=True, timeout=10)
        print("  [OK] Sincronizado")
        return True
    except Exception as e:
        print(f"  [WARN] Deploy: {e}")
        return False
