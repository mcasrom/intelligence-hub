# daily_news — Roadmap

## Filosofía

> Laptop solo para test/desarrollo. Producción corre en heznert vía APIs externas (Groq + Gemini). Sin GPU necesaria.

## Fases

### FASE 0 — Fundación (ahora)
- [x] Evaluar recursos: laptop (15GB/12c), heznert (4GB/2c/38GB), Pi (descartado)
- [x] Definir arquitectura híbrida: scraping ligero + APIs cloud + static deploy
- [ ] `config.yml` con 17 fuentes RSS de 7 países
- [ ] `src/db.py` — SQLite schema (articles, clusters, sync_events, word_frequencies)
- [ ] `src/rotation.py` — Rate limiting + cache con backoff exponencial
- [ ] `src/scraper.py` — RSS collector con feedparser
- [ ] `src/embeddings.py` — Gemini API (production) / Ollama (test)
- [ ] `src/clusterer.py` — HDBSCAN clustering sobre embeddings
- [ ] `src/sync_detector.py` — Detectar misma noticia multi-fuente por similitud coseno
- [ ] `src/analytics.py` — Word tracking 3/5/7 días + TF-IDF keywords
- [ ] `src/llm.py` — Groq (production) / Ollama (test) para etiquetar clusters
- [ ] `src/generator.py` — Jinja2 → HTML estático + JSON data
- [ ] `src/deploy.py` — Git push a GitHub Pages + rsync a heznert
- [ ] `main.py` — Orquestador completo
- [ ] Test end-to-end en laptop (modo test con Ollama)

### FASE 1 — Core scraping & almacenamiento
- [ ] Scraper corriendo en heznert via cron (cada 6h)
- [ ] SQLite poblándose con artículos de todas las fuentes
- [ ] Rate limiting respetando TTL de cada feed
- [ ] Cache de respuestas para no repetir requests

### FASE 2 — Clustering & detección de sincronizadas
- [ ] Embeddings de titulares vía Gemini API (production)
- [ ] HDBSCAN clustering sobre ventana de 7 días
- [ ] Detección de noticias sincronizadas (misma historia en ≥2 fuentes)
- [ ] Etiquetado de clusters vía Groq API
- [ ] Alertas de breaking news (pico repentino en un clúster)

### FASE 3 — Analítica de palabras
- [ ] Extracción de keywords por artículo
- [ ] Ventanas de 3/5/7 días con top-N palabras
- [ ] Trending topics: palabras que suben/bajan respecto a días anteriores
- [ ] Word clouds generados automáticamente

### FASE 4 — Generación HTML & deploy
- [ ] Template Jinja2 para daily briefing (como el actual)
- [ ] Página de clústeres con artículos agrupados
- [ ] Página de palabras trending (3/5/7 días)
- [ ] Página de sincronizadas con mapa de fuentes
- [ ] Deploy automático a GitHub Pages
- [ ] rsync a heznert para servirlos desde nginx

### FASE 5 — Editoriales sincronizados
- [ ] Detectar editoriales por patrones de texto ("editorial", "opinión", "Thréard", etc.)
- [ ] Comparar ángulos editoriales sobre un mismo tema
- [ ] Visualización de líneas editoriales por país/medio

### FASE 6 — Producción
- [ ] Migrar scraping + generación a heznert
- [ ] Groq + Gemini como backend de IA (sin Ollama en prod)
- [ ] Cron estable con logging y alertas de fallo
- [ ] GitHub Actions como fallback de build

### FASE 7 — Mejoras continuas
- [ ] Detección de narrativas (palabras que evolucionan 7+ días)
- [ ] API REST ligera en heznert para servir datos JSON
- [ ] Panel de control web con gráficos
- [ ] Notificaciones Telegram de clústeres importantes
- [ ] Integración GDELT (como en verificacion_news)

## Estructura final

```
~/daily_news/
├── config.yml              # Fuentes, APIs, thresholds
├── main.py                 # Orquestador
├── requirements.txt        # Dependencias
├── ROADMAP.md              # Este archivo
├── src/
│   ├── __init__.py
│   ├── db.py               # SQLite schema + queries
│   ├── scraper.py          # RSS collector
│   ├── rotation.py         # Rate limiting + cache
│   ├── embeddings.py       # Gemini / Ollama embeddings
│   ├── clusterer.py        # HDBSCAN clustering
│   ├── sync_detector.py    # Cross-source sync detection
│   ├── analytics.py        # Word tracking + TF-IDF
│   ├── llm.py              # Groq / Ollama LLM
│   ├── generator.py        # Jinja2 → HTML
│   └── deploy.py           # Git push + rsync
├── data/
│   ├── news.db             # SQLite
│   └── cache/              # Feed cache
├── output/                 # HTML generado (deploy/)
│   ├── index.html
│   ├── clusters.html
│   ├── 260723_day_briefing.html
│   └── data.json
├── deploy/                 # rsync target
└── templates/              # Jinja2 templates
    ├── base.html
    ├── briefing.html
    ├── clusters.html
    └── analytics.html
```

## Notas técnicas

- **Embeddings**: Gemini `models/embedding-001` (768d, gratis 1500 req/día). En test: Ollama mxbai-embed-large.
- **LLM**: Groq `llama3-70b-8192` (30 req/min gratis). En test: Ollama qwen3:4b.
- **Clustering**: HDBSCAN con `min_cluster_size=2` para capturar pares sincronizados.
- **Rate limiting**: 15 min entre requests al mismo feed. Backoff 2^n + jitter.
- **Cache**: TTL 30 min en RAM para evitar re-fetches.
- **Deploy**: `git push` a GitHub Pages + `rsync` opcional a heznert.
