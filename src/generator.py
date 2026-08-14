import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / 'templates'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'


def _ensure_dirs():
    TEMPLATES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def _parse_date(date_str):
    s = date_str.strip()
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S %Z',
        '%d %b %Y %H:%M:%S %z',
        '%d %b %Y %H:%M:%S %Z',
        '%d %b %Y %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%d/%m/%Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s)
    except Exception:
        return None

def _article_matches_date(article, date_str):
    published = article.get('published')
    if not published:
        return False
    dt = _parse_date(published)
    if dt is None:
        return False
    try:
        article_date = dt.strftime('%y%m%d')
        return article_date == date_str
    except Exception:
        return False


def generate_briefing(articles, clusters, sync_events, frequencies, trends, date_str=None, stance_data=None, coordination_flags=None, all_articles_in_window=None,
                      sources=None, llm_model=None, wordclouds=None,
                      breaking=None, entities=None, site_domain=None,
                      feed_status=None, is_index=True):
    _ensure_dirs()
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime('%y%m%d')

    archive = []
    for i in range(7):
        d = datetime.now(timezone.utc) - timedelta(days=i)
        ds = d.strftime('%y%m%d')
        f = OUTPUT_DIR / f'{ds}_day_briefing.html'
        archive.append({'date': ds, 'exists': f.exists(), 'label': d.strftime('%d/%m/%y')})

    # ── KPI Chart Data ──────────────────────────────────────────────
    now_local = datetime.now(timezone.utc)
    # Ancla de contenido: si la edición de hoy aún no tiene noticias (madrugada),
    # se ancla al día más reciente que sí tiene, para que la portada nunca quede vacía.
    MIN_ARTICLES = 5
    today_str = now_local.strftime('%y%m%d')
    anchor = now_local
    if date_str == today_str:
        day_counts = []
        for i in range(7):
            d = now_local - timedelta(days=i)
            c = sum(1 for a in articles if _article_matches_date(a, d.strftime('%y%m%d')))
            day_counts.append((d, c))
        if day_counts[0][1] < MIN_ARTICLES:
            for d, c in day_counts[1:]:
                if c >= MIN_ARTICLES:
                    anchor = d
                    break
    content_ds = anchor.strftime('%y%m%d')
    content_note = ""
    if content_ds != today_str:
        content_note = f"Mostrando noticias del {anchor.strftime('%d/%m/%Y')} — aún no hay novedades de hoy."
    chart_data = {'labels': [], 'articles': [], 'sources': [], 'clusters': [], 'editions': []}
    for i in range(6, -1, -1):
        d = anchor - timedelta(days=i)
        ds = d.strftime('%y%m%d')
        label = d.strftime('%d/%m')
        chart_data['labels'].append(label)
        day_arts = [a for a in articles if _article_matches_date(a, ds)]
        chart_data['articles'].append(len(day_arts))
        active_srcs = len(set(a['source'] for a in day_arts))
        chart_data['sources'].append(active_srcs)
        day_clusters = sum(1 for c in clusters.values() if any(
            _article_matches_date(a, ds) for a in c.get('articles', [])
        ))
        chart_data['clusters'].append(day_clusters)
        edition_file = OUTPUT_DIR / f'{ds}_day_briefing.html'
        chart_data['editions'].append(ds if edition_file.exists() else None)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template('briefing.html')

    articles = [a for a in articles if _article_matches_date(a, content_ds)]

    # Filter cluster articles to match the edition date
    filtered_clusters = {}
    for cid, cdata in clusters.items():
        fc = dict(cdata)
        fc['articles'] = [a for a in cdata.get('articles', []) if _article_matches_date(a, content_ds)]
        fc['size'] = len(fc['articles'])
        if fc['size'] >= 2:
            filtered_clusters[cid] = fc
    clusters = filtered_clusters

    MAX_ARTICLES_PER_SOURCE = 8

    by_country = {}
    for a in articles:
        country = a.get('country', 'internacional')
        if country not in by_country:
            by_country[country] = {}
        source = a['source']
        if source not in by_country[country]:
            by_country[country][source] = []
        if len(by_country[country][source]) < MAX_ARTICLES_PER_SOURCE:
            by_country[country][source].append(a)

    real_counts = {}
    # Only count articles matching the current edition date
    for a in (all_articles_in_window or articles):
        if _article_matches_date(a, content_ds):
            c = a.get('country', 'internacional')
            real_counts[c] = real_counts.get(c, 0) + 1

    all_sources = {}
    for country_key, feeds in (sources or {}).items():
        display_country = country_key.replace('_', ' ').title()
        all_sources[display_country] = {'sources': {}, 'total': real_counts.get(country_key, 0)}
        for feed in feeds:
            src_name = feed['name']
            lang = feed.get('lang', '')
            found_articles = by_country.get(country_key, {}).get(src_name, [])
            count = len(found_articles)
            all_sources[display_country]['sources'][src_name] = {
                'articles': found_articles,
                'lang': lang,
                'url': feed.get('url', ''),
                'count': count,
            }

    html = template.render(
        date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        date_str=date_str,
        by_country=by_country,
        all_sources=all_sources,
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
        stance_data=stance_data or {},
        coordination_flags=coordination_flags or [],
        site_domain=site_domain or 'viajeinteligencia.com',
        archive=archive,
        chart_data=chart_data,
        total_articles=len(articles),
        total_clusters=len(clusters),
        content_note=content_note,
        generated_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    )

    output_path = OUTPUT_DIR / f'{date_str}_day_briefing.html'
    output_path.write_text(html, encoding='utf-8')
    print(f'  [OK] Briefing generado: {output_path}')
    if is_index:
        index_path = OUTPUT_DIR / 'index.html'
        # Publicación protegida: NUNCA dejar la portada vacía. Si el contenido
        # filtrado es insuficiente, se conserva la última portada buena.
        has_content = len(articles) >= MIN_ARTICLES or bool(
            clusters and any(len(c.get('articles', [])) >= 2 for c in clusters.values()))
        if has_content:
            index_path.write_text(html, encoding='utf-8')
            print(f'  [OK] Index actualizado: {index_path}')
        else:
            print(f'  [WARN] Index NO sobrescrito (contenido insuficiente: {len(articles)} artículos) — se mantiene la última portada.')
    return output_path


def generate_clusters_page(clusters, date_str=None):
    _ensure_dirs()
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime('%y%m%d')
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template('clusters.html')
    html = template.render(
        date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        date_str=date_str,
        clusters=clusters,
        generated_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    )
    output_path = OUTPUT_DIR / 'clusters.html'
    output_path.write_text(html, encoding='utf-8')
    print(f'  [OK] Clusters generados: {output_path}')


def generate_json_data(articles, clusters, sync_events, frequencies, trends, date_str=None):
    _ensure_dirs()
    data = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_articles': len(articles),
        'articles': articles[:100],
        'clusters': list(clusters.values()) if isinstance(clusters, dict) else clusters,
        'sync_events': sync_events[:20],
        'word_frequencies': frequencies,
        'trends': trends,
    }
    output_path = OUTPUT_DIR / 'data.json'
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  [OK] JSON data: {output_path}')


def generate_health_json(run_id, start_time, total_articles, total_clusters, total_syncs,
                          feeds_ok, feeds_fail, errors=None, duration=None):
    _ensure_dirs()
    now = datetime.now(timezone.utc)
    critical_errors = [e for e in (errors or []) if "429" not in e and "LLM" not in e]
    health = {
        "status": "ok" if not critical_errors else "degraded",
        "run_id": run_id,
        "generated_at": now.isoformat(),
        "pipeline_date": start_time.strftime("%Y-%m-%d"),
        "pipeline_time": start_time.strftime("%H:%M:%S UTC"),
        "duration_seconds": round(duration, 1) if duration else None,
        "total_articles": total_articles,
        "total_clusters": total_clusters,
        "total_syncs": total_syncs,
        "feeds_ok": feeds_ok,
        "feeds_fail": feeds_fail,
        "feeds_total": feeds_ok + feeds_fail,
        "errors": errors or [],
        "version": "2.0",
    }
    output_path = OUTPUT_DIR / "health.json"
    output_path.write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'  [OK] Health JSON: {output_path}')
    return health


def generate_portada(articles, clusters, sync_events, date_str=None):
    """Portada tipo medio de noticias (lector). Reutiliza los clusters existentes."""
    _ensure_dirs()
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime('%y%m%d')

    # Clusters con >=2 artículos, ordenados por tamaño desc
    ordered = []
    for cid, cdata in (clusters or {}).items():
        # Excluir ruido: cluster_id -1 (artículos sin agrupar) no es un tema real
        if cid is None or str(cid) == '-1' or cid == -1:
            continue
        arts = [a for a in cdata.get('articles', [])]
        if len(arts) >= 2:
            # Título del tema: usar el artículo más largo/representativo (primer artículo de la lista,
            # que el pipeline suele ordenar por relevancia). Limpiar para que sea un titular.
            best = max(arts, key=lambda a: len(a.get('title', '') or ''))
            label = best.get('title', 'Tema')[:90]
            ordered.append({
                'id': cid,
                'title': label,
                'size': len(arts),
                'articles': arts[:4],
                'sources': sorted(set(a.get('source', '?') for a in arts))[:4],
            })
    ordered.sort(key=lambda c: -c['size'])

    # Sincronizadas (misma noticia multi-fuente)
    synced = []
    for s in (sync_events or [])[:8]:
        if isinstance(s, dict):
            synced.append({'title': s.get('title', ''), 'sources': s.get('sources', [])})

    # Trending palabras (si se pasan, opcional)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template('portada.html')
    html = template.render(
        date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        date_str=date_str,
        clusters=ordered,
        synced=synced,
        total_articles=len(articles),
        total_clusters=len(ordered),
        generated_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
    )
    output_path = OUTPUT_DIR / 'portada.html'
    output_path.write_text(html, encoding='utf-8')
    print(f'  [OK] Portada lector generada: {output_path} ({len(ordered)} temas)')
    return output_path

