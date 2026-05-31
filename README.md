# stressing-tools

Benchmark suite para **comparar la performance de distintos lenguajes y frameworks bajo carga HTTP**.

Cada target es un servidor HTTP mínimo, dockerizado y limitado a los mismos recursos
(**1 CPU / 512 MB**), de modo que las mediciones reflejen el costo real del runtime/framework
y no diferencias de hardware. La carga se genera con [k6](https://k6.io/), que corre en el
**host** (no en Docker) para no contaminar las mediciones con el overhead del contenedor de carga.

El resultado es una tabla comparativa con latencia (p50/p95/p99), throughput, error rate y uso
de CPU y memoria (pico/promedio) por target — disponible en Markdown y como
[reporte HTML interactivo con columnas ordenables](https://juaiglesias.github.io/stressing-tools/).

## Targets

`config/targets.json` es la única fuente de verdad de los targets.

| target              | tecnología           | port host | endpoint        |
|---------------------|----------------------|-----------|-----------------|
| node-express        | node + express       | 3001      | /holamundo      |
| node-fastify        | node + fastify       | 3002      | /holamundo      |
| node-nestjs         | node + nestjs        | 3003      | /holamundo      |
| php-laravel         | php + laravel        | 3004      | /api/holamundo  |
| python-fastapi      | python + fastapi     | 3005      | /holamundo      |
| php-laravel-octane  | php + laravel-octane | 3006      | /api/holamundo  |
| php-laravel-fpm     | php + laravel-fpm    | 3007      | /api/holamundo  |
| go-gin              | go + gin             | 3008      | /holamundo      |
| rust-axum           | rust + axum          | 3009      | /holamundo      |

**Invariantes de todo target:**
- Escucha internamente en el puerto **3000** (el port del registry es solo el mapeo al host).
- La imagen incluye `curl` (lo usa el healthcheck del compose).
- Expone al menos el endpoint del scenario `holamundo` devolviendo HTTP 200.

## Scenarios

`config/scenarios.json` es la única fuente de verdad de los scenarios.

| scenario   | archivo                 | método | descripción                                                         |
|------------|-------------------------|--------|---------------------------------------------------------------------|
| holamundo  | scenarios/holamundo.js  | GET    | GET básico sin I/O, mide throughput puro del framework              |
| dbquery    | scenarios/dbquery.js    | GET    | simula acceso a DB (I/O wait ~25ms), mide el modelo de concurrencia |
| cpucompute | scenarios/cpucompute.js | GET    | CPU-bound: O(n²) + O(C³) matrix multiply, mide cómputo crudo       |
| memalloc   | scenarios/memalloc.js   | GET    | aloca N objetos anidados y serializa, mide presión de allocator/GC  |
| payload    | scenarios/payload.js    | POST   | deserializa+valida+serializa un JSON mediano, mide parsing de input  |

Cada scenario es un script k6 que lee `__ENV.TARGET_URL`, `__ENV.TEST_PATH` y `__ENV.TEST_METHOD`
(inyectados por el runner), de modo que el mismo script sirve para todos los targets.

## Requisitos del host

- Docker + Docker Compose
- [k6](https://k6.io/docs/get-started/installation/) (`brew install k6` / `apt install k6`)
- Python 3.10+ (scripts de generación y comparación)
- `jq` (lo usa el runner bash para leer los registries)

## Uso

```bash
# 1. (primera vez, o tras agregar/quitar/deshabilitar un target) regenerar el compose
python3 scripts/generate_compose.py

# 2. benchmark completo (todos los targets × todos los scenarios enabled)
./scripts/run_benchmark.sh

# 3. benchmark selectivo
./scripts/run_benchmark.sh --targets node-express,node-fastify
./scripts/run_benchmark.sh --scenarios holamundo
./scripts/run_benchmark.sh --targets express --scenarios holamundo   # acepta nombre corto
```

`--targets` acepta el nombre completo (`node-express`) o el corto (`express`).

### Qué hace `run_benchmark.sh`

1. Resuelve qué targets y scenarios correr (filtros + `enabled` en los registries).
2. `docker compose up -d --build` de los servicios seleccionados.
3. Espera a que cada container esté `healthy` (timeout 90s; si falla, dumpea logs y aborta).
4. Por cada par target×scenario: lanza `docker stats` en background y corre `k6 run` con las env vars.
5. Vuelca el JSON de k6 a `results/<target>_<scenario>_<ts>.json` y los stats a `..._stats.jsonl`.
6. Corre `compare_results.py`, que genera `reports/comparison_<ts>.md` (tabla ordenada por p95
   ascendente, con latencias, throughput, error rate, CPU y memoria).

## Estructura del repositorio

```
config/
  targets.json       ← registro de targets (única fuente de verdad)
  scenarios.json     ← registro de scenarios k6 (única fuente de verdad)

targets/             ← un subdirectorio por target, cada uno con su Dockerfile
  node-express/        express minimal
  node-fastify/        fastify minimal
  node-nestjs/         nestjs (build TypeScript)
  python-fastapi/      fastapi + uvicorn --workers 4
  php-laravel/         laravel, artisan serve
  php-laravel-fpm/     laravel sobre php-fpm + nginx (supervisord)
  php-laravel-octane/  laravel octane sobre swoole, 4 workers
  go-gin/              gin (binario compilado, imagen alpine)
  rust-axum/           axum + tokio (multi-stage build, imagen alpine)

scenarios/
  holamundo.js       ← GET básico sin I/O, 50 VUs
  dbquery.js         ← GET con I/O wait ~25ms, 100 VUs
  cpucompute.js      ← GET CPU-bound O(n²)+O(C³), 20 VUs
  memalloc.js        ← GET con N objetos vivos, 20 VUs
  payload.js         ← POST JSON parse/validate/serialize, 50 VUs

scripts/
  generate_compose.py  ← genera docker-compose.yml desde targets.json
  generate_html.py     ← genera reporte HTML interactivo desde el Markdown
  run_benchmark.sh     ← orquestador principal (levanta containers, corre k6, compara)
  compare_results.py   ← genera tabla comparativa Markdown desde el JSON de k6

docker-compose.yml   ← GENERADO desde targets.json — no editar a mano
results/             ← gitignored, NDJSON de k6 + JSONL de docker stats
reports/             ← commiteados, tablas comparativas en Markdown + HTML por run
docs/
  index.html         ← reporte HTML más reciente (GitHub Pages)
```

## Resource limits por container

Cada container está limitado a **1 CPU y 512 MB RAM** (definido en el `docker-compose.yml`
generado). Para cambiar los límites, modificar `scripts/generate_compose.py` y regenerar —
no editar el compose a mano.

## Resultados

> Benchmark corrido en host con 1 CPU / 512 MB por container. [Ver reporte interactivo →](https://juaiglesias.github.io/stressing-tools/)

### holamundo — throughput puro (GET sin I/O)

| target             | req/s    | p50 (ms) | p95 (ms) | peak Mem |
|--------------------|----------|----------|----------|----------|
| **rust-axum**      | 61,158   | 0.66     | 0.90     | 5.5 MB   |
| node-fastify       | 32,479   | 1.03     | 2.23     | 20.1 MB  |
| go-gin             | 18,321   | 0.44     | 1.39     | 20.9 MB  |
| node-nestjs        | 8,788    | 3.93     | 9.73     | 36.3 MB  |
| node-express       | 8,190    | 3.56     | 13.88    | 29.0 MB  |
| python-fastapi     | 3,950    | 2.30     | 79.18    | 157.8 MB |
| php-laravel-octane | 993      | 7.65     | 93.38    | 163.2 MB |
| php-laravel        | 710      | 60.86    | 106.12   | 57.6 MB  |
| php-laravel-fpm    | 342      | 102.18   | 200.22   | 94.6 MB  |

### dbquery — concurrencia bajo I/O (sleep ~25ms simulando DB)

| target             | req/s  | p50 (ms) | p95 (ms) | peak CPU |
|--------------------|--------|----------|----------|----------|
| node-fastify       | 3,091  | 25.80    | 27.14    | 31.9%    |
| go-gin             | 3,073  | 25.90    | 26.99    | 44.4%    |
| **rust-axum**      | 2,973  | 26.83    | 28.15    | 18.0%    |
| python-fastapi     | 2,895  | 27.30    | 30.70    | 82.5%    |
| node-nestjs        | 2,922  | 26.93    | 30.85    | 76.5%    |
| node-express       | 2,886  | 27.28    | 31.49    | 68.7%    |
| php-laravel-fpm    | 295    | 302.21   | 398.78   | 104.6%   |
| php-laravel-octane | 148    | 663.94   | 677.99   | 41.9%    |
| php-laravel        | 35     | 2809.78  | 2853.46  | 16.4%    |

### cpucompute — cómputo crudo (O(n²) + O(C³), n=200, C=64)

| target             | req/s  | p50 (ms) | p95 (ms) | peak Mem |
|--------------------|--------|----------|----------|----------|
| **rust-axum**      | 2,366  | 8.52     | 9.11     | 5.2 MB   |
| node-fastify       | 2,154  | 8.35     | 11.84    | 27.6 MB  |
| node-nestjs        | 1,787  | 9.72     | 17.20    | 35.7 MB  |
| node-express       | 1,780  | 9.73     | 18.13    | 28.0 MB  |
| go-gin             | 991    | 1.32     | 95.11    | 21.0 MB  |
| php-laravel        | 203    | 93.12    | 108.68   | 58.3 MB  |
| php-laravel-octane | 183    | 98.05    | 179.00   | 164.1 MB |
| php-laravel-fpm    | 98     | 196.74   | 303.56   | 97.3 MB  |
| python-fastapi     | 34     | 496.99   | 904.62   | 157.0 MB |

### memalloc — presión de allocator/GC (20k objetos anidados vivos)

| target             | req/s | p50 (ms) | p95 (ms) | peak Mem  |
|--------------------|-------|----------|----------|-----------|
| php-laravel        | 146   | 129.74   | 150.24   | 77.7 MB   |
| node-express       | 117   | 126.63   | 199.15   | 62.8 MB   |
| node-fastify       | 114   | 128.64   | 201.54   | 68.4 MB   |
| node-nestjs        | 100   | 191.36   | 220.76   | 60.2 MB   |
| php-laravel-octane | 96    | 197.13   | 281.37   | 244.4 MB  |
| php-laravel-fpm    | 48    | 394.74   | 699.00   | 493.4 MB  |
| **rust-axum**      | 38    | 547.90   | 585.73   | 34.9 MB   |
| python-fastapi     | 31    | 490.49   | 1096.04  | 278.1 MB  |
| go-gin             | 27    | 597.34   | 1198.57  | 511.9 MB  |

### payload — parsing JSON (POST 100 items, filter + transform)

| target             | req/s  | p50 (ms) | p95 (ms) | peak Mem |
|--------------------|--------|----------|----------|----------|
| node-fastify       | 13,223 | 3.03     | 6.16     | 33.1 MB  |
| **rust-axum**      | 9,250  | 3.86     | 9.21     | 7.3 MB   |
| node-express       | 5,611  | 6.69     | 15.65    | 30.7 MB  |
| node-nestjs        | 5,454  | 6.86     | 16.68    | 38.5 MB  |
| go-gin             | 3,283  | 1.08     | 91.03    | 44.6 MB  |
| python-fastapi     | 1,534  | 6.14     | 88.09    | 238.5 MB |
| php-laravel-octane | 628    | 88.41    | 103.28   | 244.0 MB |
| php-laravel        | 554    | 81.08    | 119.69   | 59.8 MB  |
| php-laravel-fpm    | 269    | 196.20   | 295.47   | 120.6 MB |

### Observaciones clave

- **rust-axum** domina en holamundo (61k req/s, 5.5 MB) y cpucompute — mínimo consumo de memoria en todos los scenarios.
- **node-fastify** es el más rápido en payload (JSON parsing) y consistentemente eficiente en I/O.
- **go-gin** tiene p50 bajo pero p95 alto en scenarios con GC (holamundo, payload, memalloc) — stop-the-world visible bajo carga.
- **dbquery** (I/O bound): rust-axum usa solo 18% CPU vs 44% de go-gin para el mismo throughput — Tokio aprovecha mejor el thread pool con I/O puro.
- **memalloc** invierte el ranking: sin GC, Rust paga cada allocación; Node.js y PHP (que recicla por request) son más eficientes.
- **python-fastapi** (uvicorn 4 workers) compite bien en I/O pero cae ante CPU-bound por el GIL.
- **PHP Laravel** (artisan serve) sorprende en memalloc gracias al modelo share-nothing (proceso fresco por request).

## Extender el benchmark

El proyecto incluye dos skills de Claude Code que guían el flujo:

- **add-target** — agregar un nuevo lenguaje/framework al benchmark.
- **add-scenario** — agregar un nuevo tipo de prueba k6.
