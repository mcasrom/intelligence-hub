from datetime import datetime, timezone, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _ensure_dirs():
    TEMPLATES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def generate_briefing(articles, clusters, sync_events, frequencies, trends, date_str=None,
                      sources=None, llm_model=None, wordclouds=None,
                      breaking=None, entities=None, site_domain=None,
                      feed_status=None):
    _ensure_dirs()
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%y%m%d")

    archive = []
    for i in range(7):
        d = datetime.now(timezone.utc) - timedelta(days=i)
        ds = d.strftime("%y%m%d")
        f = OUTPUT_DIR / f"{ds}_day_briefing.html"
        archive.append({"date": ds, "exists": f.exists(), "label": d.strftime("%d/%m/%y")})

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("briefing.html")

    by_country = {}
    for a in articles:
        country = a.get("country", "internacional")
        if country not in by_country:
            by_country[country] = {}
        source = a["source"]
        if source not in by_country[country]:
            by_country[country][source] = []
        by_country[country][source].append(a)

    html = template.render(
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        date_str=date_str,
        by_country=by_country,
        clusters=clusters,
        sync_events=sync_events,
        frequencies=frequencies,
        trends=trends,
        sources=sources or {},
        llm_model=llm_model,
        wordclouds=wordclouds or {},
        breaking=breaking or [],
        entities=entities or {},
        feed_status=feed_status or [],
        site_domain=site_domain or "viajeinteligencia.com",
        archive=archive,
        total_articles=len(articles),
        total_clusters=len(clusters),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )

    output_path = OUTPUT_DIR / f"{date_str}_day_briefing.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  [OK] Briefing generado: {output_path}")

    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"  [OK] Index actualizado: {index_path}")

    return output_path


def generate_clusters_page(clusters, date_str=None):
    _ensure_dirs()
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%y%m%d")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("clusters.html")

    html = template.render(
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        date_str=date_str,
        clusters=clusters,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )

    output_path = OUTPUT_DIR / "clusters.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  [OK] Clusters generados: {output_path}")


def generate_json_data(articles, clusters, sync_events, frequencies, trends, date_str=None):
    _ensure_dirs()
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": len(articles),
        "articles": articles[:100],
        "clusters": list(clusters.values()) if isinstance(clusters, dict) else clusters,
        "sync_events": sync_events[:20],
        "word_frequencies": frequencies,
        "trends": trends,
    }
    output_path = OUTPUT_DIR / "data.json"
    import json
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] JSON data: {output_path}")
