#!/usr/bin/env python3
"""notify_ingesta.py — Resumen de la ingesta de news para el bot dailynews.

Se ejecuta al terminar cada ingesta (run.sh, cada 3h). Lee el ultimo entry de
cron_log.json y envia al bot dailynews un resumen con "colores semanticos"
(emojis + negrita, ya que Telegram HTML no soporta colores de texto reales):

  🟢 todo ok / 🟡 avisos (feeds_fail>0) / 🔴 fallo (status!=completed)

Uso:
    python3 notify_ingesta.py            # envia resumen de la ultima ingesta
    python3 notify_ingesta.py --force    # envía aunque ya se avisó de este run_id
"""
import json, os, sys, glob, gzip, re, ipaddress
from datetime import datetime, timezone, timedelta
from pathlib import Path

HUB = Path(__file__).parent
CRON_LOG = HUB / "cron_log.json"
STATE = HUB / ".notify_ingesta_last"   # evita avisar 2x del mismo run_id

# --- Accesos reales al ecosistema (mismo clasificador QUE EL KPI) ---
# Copia fiel de 180826_kpi_total.py: solo hosts viajeinteligencia.com y
# considera "human" SOLO al trafico humano real (no bots/dev/internal).
ACCESS_LINE = re.compile(
    r"^(?P<ip>\S+) - - \[(?P<ts>[^\]]+)\] \"(?P<method>\S+) (?P<path>[^\" ]*)[^\"]*\" "
    r"(?P<status>\d+) (?P<size>\d+) \"(?P<ref>[^\"]*)\" \"(?P<ua>[^\"]*)\"+\s+host=(?P<host>\S+)$")
DAYM = re.compile(r"(\d{1,2})/([A-Za-z]{3})/(\d{4})")
_OWN_UA = re.compile(r"ecosystem-healthcheck|uptime.?kuma|UptimeRobot|node-fetch|axios|requests/|Go-http-client|curl/|Wget|python-requests", re.I)
_BOT = re.compile(r"bot\b|crawl|spider|scrape|slurp|monitor|pingdom|Googlebot|bingbot|Yandex|Baidu|DuckDuckBot|facebookexternalhit|Twitterbot|Pinterest|LinkedInBot|Discordbot|TelegramBot|Semrush|ahrefs|MJ12|DotBot|GPTBot|ClaudeBot|Amazonbot|Bytespider|CCBot|Applebot|http\.client|Guzzle|okhttp|Java/|Python|httpx|aiohttp|Scrapy|Censys|Shodan|Netcraft", re.I)
_INTERNAL_NETS = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128"),
                  ipaddress.ip_network("172.16.0.0/12"), ipaddress.ip_network("10.0.0.0/8"),
                  ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("2a0c:5a83:c505::/48")]
_INTERNAL_IPS = {"178.105.80.193", "172.20.0.2", "172.17.0.2", "2a01:4f8:"}
_DEV_IPS = {"79.116.225.118", "79.116.225.109", "79.116.111.15"}
_CRAWLER_IPS = {"47.76.149.155", "47.107.156.154", "167.99.82.80", "176.230.191.189",
                "77.132.115.145", "49.43.245.77", "93.88.156.4", "103.125.235.21",
                "217.130.92.204", "216.73.216.187", "195.178.110.199",
                "2409:40f2:318:f11f:66d0:3307:f2d9:11bf", "159.26.104.77",
                "103.69.77.20", "42.108.30.112"}
_CRAWLER_NETS = [ipaddress.ip_network("2409:40f2:318:f11f::/64"),
                 ipaddress.ip_network("216.73.216.0/24"),
                 ipaddress.ip_network("185.177.72.0/24")]
_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

def _classify(ip, ua):
    try:
        a = ipaddress.ip_address(ip)
        for net in _INTERNAL_NETS:
            if a in net:
                return "internal"
    except Exception:
        return "human"
    if ip in _INTERNAL_IPS or ip.startswith("2a01:4f8:"):
        return "internal"
    if _OWN_UA.search(ua):
        return "internal"
    if ip in _DEV_IPS:
        return "dev"
    try:
        a = ipaddress.ip_address(ip)
        for net in _CRAWLER_NETS:
            if a in net:
                return "bot"
    except Exception:
        pass
    if ip in _CRAWLER_IPS:
        return "bot"
    if _BOT.search(ua):
        return "bot"
    return "human"

def count_hoy():
    """Devuelve (humanos_hoy, maquinas_hoy). Mismo criterio que
    160826_Weekly_Access.py --hoy: humano vs maquina SOLO del dia actual."""
    now = datetime.now(timezone.utc)
    today_month = now.strftime("%b")
    today_day = now.day
    year = now.year
    h_hum = m_maq = 0
    for fn in glob.glob("/var/log/nginx/access.log*"):
        opener = gzip.open if fn.endswith(".gz") else open
        try:
            f = opener(fn, "rt", errors="replace")
        except OSError:
            continue
        with f:
            for line in f:
                m = ACCESS_LINE.match(line.rstrip("\n"))
                if not m:
                    continue
                g = m.groupdict()
                host = g["host"]
                if not host.endswith("viajeinteligencia.com"):
                    continue
                dm = DAYM.search(g["ts"])
                # comparamos dia + mes + año (no solo el mes!)
                if not dm or int(dm.group(1)) != today_day \
                   or dm.group(2) != today_month or int(dm.group(3)) != year:
                    continue
                if _classify(g["ip"], g["ua"]) == "human":
                    h_hum += 1
                else:
                    m_maq += 1
    return h_hum, m_maq

def load_env():
    env = {}
    try:
        for line in (HUB / ".env").read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env

def last_entry():
    try:
        data = json.loads(CRON_LOG.read_text())
    except (OSError, ValueError):
        return None
    entries = data if isinstance(data, list) else [data]
    return entries[0] if entries else None

def local_ts(iso_ts):
    """Convierte ISO UTC a hora local España (UTC+2 en verano) legible."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)  # normaliza a utc
        # España verano = UTC+2
        local = dt.replace(tzinfo=timezone.utc).astimezone(
            timezone(timedelta(hours=2)))
        return local.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_ts or "?"

def main():
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[WARN] sin TELEGRAM_BOT_TOKEN/CHAT_ID, no se notifica")
        return 0

    e = last_entry()
    if not e:
        print("[WARN] cron_log.json vacio o ilegible")
        return 1

    run_id = e.get("run_id", "?")
    # evitar duplicados del mismo run_id (salvo --force)
    if "--force" not in sys.argv:
        try:
            if STATE.read_text().strip() == run_id:
                return 0
        except OSError:
            pass

    status = e.get("status", "?")
    articles = e.get("articles", 0)
    clusters = e.get("clusters", 0)
    feeds_ok = e.get("feeds_ok", 0)
    feeds_fail = e.get("feeds_fail", 0)
    duration = e.get("duration", 0)
    errors = e.get("errors")
    ts = local_ts(e.get("timestamp", ""))

    # color semantico
    if status != "completed" or feeds_fail:
        emoji, tag, color = "\U0001F534", "FALLO", None     # 🔴
    elif feeds_fail:
        emoji, tag, color = "\U0001F7E1", "AVISOS", None   # 🟡
    else:
        emoji, tag, color = "\U0001F7E2", "CORRECTO", None # 🟢

    lines = [
        f"{emoji} <b>Ingesta news · {tag}</b>",
        f"🕒 <b>{ts}</b>",
        f"📰 artículos: <b>{articles}</b>",
        f"☁️ clústeres: <b>{clusters}</b>",
    ]
    # Accesos reales HOY (humano / maquina), mismo criterio que el semanal
    acc_h, acc_m = count_hoy()
    lines.append(f"🖥️ accesos: <b>{acc_h}H</b> / <b>{acc_m}M</b>")
    if errors:
        lines.append(f"⚠️ errors: <i>{errors}</i>")
    if feeds_fail:
        lines.append(f"⚠️ feeds fallidos: <b>{feeds_fail}</b> (<i>{feeds_ok} ok</i>)")
    else:
        lines.append(f"📡 feeds: <b>{feeds_ok} ok</b>")
    lines.append(f"⏱️ duración: <b>{duration:.0f}s</b>")

    text = "\n".join(lines)
    try:
        import urllib.parse, urllib.request
        url = "https://api.telegram.org/bot%s/sendMessage" % token
        data = urllib.parse.urlencode({
            "chat_id": chat, "text": text, "parse_mode": "HTML",
        }).encode()
        urllib.request.urlopen(url, data=data, timeout=15)
    except Exception as ex:
        print("[WARN] sendMessage fallo: %s" % ex)
        return 1

    STATE.write_text(run_id)
    print("[OK] notificada ingesta %s (%s)" % (run_id, tag))
    return 0

if __name__ == "__main__":
    sys.exit(main())
