#!/usr/bin/env python3
"""Vigila feed_health y frescura por fuente. No escribe en la BD."""
from __future__ import annotations
import argparse, json, os, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path("/home/deploy/intelligence-hub")
DB=ROOT/"data/news.db"
CONFIG=ROOT/"config.yml"
STATE=ROOT/"data/feed_health_watch_state.json"
LOG=ROOT/"feed_health_watch.log"
ENV=ROOT/".env"

def load_env():
    d={}
    try:
        for ln in ENV.read_text(encoding="utf-8").splitlines():
            ln=ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k,_,v=ln.partition("="); d[k.strip()]=v.strip()
    except OSError: pass
    return d

def send(text):
    e=load_env(); tok=e.get("TELEGRAM_BOT_TOKEN",""); chat=e.get("TELEGRAM_CHAT_ID","")
    if not tok or not chat: print("[watch] sin TELEGRAM_BOT_TOKEN/CHAT_ID", file=sys.stderr); return False
    data=urllib.parse.urlencode({"chat_id":chat,"text":text,"disable_web_page_preview":"true"}).encode()
    req=urllib.request.Request("https://api.telegram.org/bot%s/sendMessage"%tok,data=data)
    try:
        with urllib.request.urlopen(req,timeout=20) as r: return r.status==200
    except Exception as e: print("[watch] Telegram fallo:",e,file=sys.stderr); return False

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dry",action="store_true"); ap.add_argument("--force",action="store_true"); a=ap.parse_args()
    import yaml
    cfg=yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    active={f["name"]: f for feeds in cfg.get("sources",{}).values() for f in feeds}
    now=datetime.now(timezone.utc)
    con=sqlite3.connect("file:%s?mode=ro"%DB,uri=True); con.row_factory=sqlite3.Row
    health={r["feed_name"]: dict(r) for r in con.execute("SELECT * FROM feed_health")}
    last={}
    for r in con.execute("SELECT source, MAX(published) AS last, COUNT(*) AS n FROM articles GROUP BY source"):
        last[r["source"]]={"last":r["last"],"n":r["n"]}
    con.close()
    findings=[]
    for name in active:
        h=health.get(name)
        if not h:
            findings.append((name,"sin_registro","no hay registro de salud"))
            continue
        try:
            lk=datetime.fromisoformat((h.get("last_ok") or "").replace("Z","+00:00"))
        except Exception:
            lk=None
        if lk and lk.tzinfo is None: lk=lk.replace(tzinfo=timezone.utc)
        age_h=(now-lk).total_seconds()/3600 if lk else 9999
        if (h.get("consecutive_failures") or 0)>=2 or age_h>6:
            findings.append((name,"caido",f"fallos={h.get('consecutive_failures',0)} · última ok hace {age_h:.1f} h"))
            continue
        l=last.get(name)
        if not l:
            findings.append((name,"sin_articulos","sin artículos en la BD"))
            continue
        try:
            lp=datetime.fromisoformat((l["last"] or "").replace("Z","+00:00"))
        except Exception:
            lp=None
        if lp and lp.tzinfo is None: lp=lp.replace(tzinfo=timezone.utc)
        days=(now-lp).total_seconds()/86400 if lp else 9999
        if days>7:
            findings.append((name,"sin_frescura",f"último artículo hace {days:.1f} d (feed ok)"))
    state={}
    try: state=json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: pass
    prev=state.get("estados",{})
    current={f"{n}:{s}" for n,s,_ in findings}
    # avisar de nuevos o cambios; no repetir el mismo estado salvo --force
    changed=[x for x in findings if a.force or f"{x[0]}:{x[1]}" not in prev]
    state["estados"]={f"{n}:{s}": True for n,s,_ in findings}
    state["checked_at"]=now.isoformat(timespec="seconds")
    if not a.dry:
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=[f"📡 Feed health · {now.strftime('%d/%m/%Y %H:%M UTC')}"]
    if not findings:
        lines.append("✅ Todos los feeds activos responden y tienen artículos recientes.")
    else:
        lines.append(f"⚠️ {len(findings)} incidencias:")
        for n,s,m in findings[:15]: lines.append(f"• {n}: {s} — {m}")
        if len(findings)>15: lines.append(f"… y {len(findings)-15} más")
    text="\n".join(lines)
    print(text)
    if changed and not a.dry:
        send(text)
    elif a.dry:
        print("(dry: no se envía)")
    return 0

if __name__=="__main__": raise SystemExit(main())
