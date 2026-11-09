# Intelligence Hub · daily_news

Ingesta y análisis de titulares de prensa internacional. El pipeline descarga
RSS, guarda artículos, calcula embeddings, agrupa temas, detecta sincronías y
publica un briefing diario y datos abiertos.

## Pipeline

- **Entrada:** 30 feeds RSS internacionales definidos en `config.yml`.
- **Ventana de clustering:** 7 días.
- **Embeddings:** `paraphrase-multilingual-MiniLM-L12-v2`.
- **Salida:** `output/` (briefing, clusters y JSON) y despliegue estático.
- **Periodicidad:** cada 3 horas; el cron arranca a los **7 minutos** para no
  coincidir con el pico de tareas del minuto 0.

## Operación

- Lanzador: `run.sh` (no versionado; vive en el servidor y se respalda aparte).
- Log principal: `cron.log`.
- Pico de memoria por ejecución: `memory.log` (`/usr/bin/time -v`).
- Base de datos: `data/news.db`.
- Los logs rotados y `memory.log` no se versionan.

## Memoria y OOM

El 2026-11-08 a las 21:11 UTC el OOM killer mató el proceso de `main.py`
durante la fase de embeddings. No fue el radar FIMI ni NearMe: fue
`intelligence-hub`, que consume el modelo de embeddings. El reintento
automático de las 21:16 terminó correctamente.

Medidas P0 aplicadas el 2026-11-09:

- cron movido de `0 */3` a `7 */3`;
- límites de hilos (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`);
- `TOKENIZERS_PARALLELISM=false` y `MALLOC_ARENA_MAX=2`;
- guarda de memoria en `run.sh` (3 GB disponibles+swap y 512 MB de swap;
  hasta tres esperas de 2 minutos);
- `torch.set_num_threads(1)` y lote de embeddings de 16.

Detalle del incidente: [`docs/OOM-2026-11-09.md`](docs/OOM-2026-11-09.md).

## Rollback

Los archivos del servidor tienen copia `*.bak-oom-20261109`. El cron anterior
está en `crontab.bak-oom-20261109`.
