# stressing-tools

## Objetivo

Benchmark suite para **comparar performance de distintos lenguajes y frameworks bajo carga HTTP**.
Cada target es un servidor HTTP mínimo, dockerizado y limitado a los mismos recursos (1 CPU / 512 MB),
de modo que las mediciones reflejen el costo real del runtime/framework y no diferencias de hardware.

k6 corre en el **host** (no en Docker) para no contaminar las mediciones con overhead del contenedor de carga.
El resultado es una tabla comparativa (latencia p50/p95/p99, throughput, error rate, CPU y memoria pico/promedio).

## Estructura de directorios

```
config/
  targets.json       ← registro de targets (única fuente de verdad: port, tests por scenario)
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
  generate_html.py     ← genera reporte HTML interactivo (también actualiza docs/index.html)
  run_benchmark.sh     ← orquestador principal (levanta containers, corre k6, compara)
  compare_results.py   ← genera tabla comparativa Markdown desde el JSON de k6

docker-compose.yml   ← GENERADO desde targets.json — no editar a mano
results/             ← gitignored, JSON NDJSON de k6 + JSONL de docker stats
reports/             ← commiteados, tablas comparativas en Markdown + HTML por run
docs/
  index.html         ← reporte HTML más reciente (GitHub Pages)
```

## Targets

`config/targets.json` es la única fuente de verdad. Estado actual:

| target              | tecnología           | port host |
|---------------------|----------------------|-----------|
| node-express        | node + express       | 3001      |
| node-fastify        | node + fastify       | 3002      |
| node-nestjs         | node + nestjs        | 3003      |
| php-laravel         | php + laravel        | 3004      |
| python-fastapi      | python + fastapi     | 3005      |
| php-laravel-octane  | php + laravel-octane | 3006      |
| php-laravel-fpm     | php + laravel-fpm    | 3007      |
| go-gin              | go + gin             | 3008      |
| rust-axum           | rust + axum          | 3009      |

Los endpoints exactos de cada scenario por target están en `config/targets.json` (campo `tests`).

**Invariantes de todo target:**
- Escucha internamente en el puerto **3000** (el port del registry es solo el mapeo al host).
- La imagen incluye `curl` (lo usa el healthcheck del compose).
- Implementa todos los scenarios declarados en su entrada `tests` de `targets.json`, devolviendo HTTP 200. Un target puede optar por no declarar un scenario (el runner imprime `SKIP`), pero lo que declare debe funcionar.

### Estructura de un target en targets.json

```json
{
  "name": "node-express",
  "language": "node",
  "framework": "express",
  "port": 3001,
  "enabled": true,
  "tests": {
    "holamundo": { "method": "GET", "path": "/holamundo" }
  }
}
```

Cada key dentro de `tests` es el nombre de un scenario. El runner lee el `method` y `path`
del target para ese scenario y los pasa a k6 vía env vars (`TEST_METHOD`, `TEST_PATH`).
Un target puede no implementar un scenario: el runner imprime `SKIP` y sigue.

## Scenarios

`config/scenarios.json` es la única fuente de verdad. Estado actual:

| scenario   | archivo                | método | descripción                                                      |
|------------|------------------------|--------|------------------------------------------------------------------|
| holamundo  | scenarios/holamundo.js | GET    | GET básico sin I/O, mide throughput puro del framework           |
| dbquery    | scenarios/dbquery.js   | GET    | simula acceso a DB (I/O wait ~25ms), mide el modelo de concurrencia |
| cpucompute | scenarios/cpucompute.js| GET    | CPU-bound: gen objetos + transform + O(n²) + O(n³), mide cómputo crudo |
| memalloc   | scenarios/memalloc.js  | GET    | aloca N objetos anidados y serializa, mide presión de allocator/GC |
| payload    | scenarios/payload.js   | POST   | deserializa+valida+serializa un JSON mediano, mide parsing de input |

Cada scenario es un script k6 que lee `__ENV.TARGET_URL`, `__ENV.TEST_PATH` y `__ENV.TEST_METHOD`
(inyectados por el runner), de modo que el mismo script sirve para todos los targets.

**Trabajo canónico** (idéntico en los 8 targets, lo que hace justa la comparación):
- `dbquery`: espera ~25ms (async donde el runtime lo permita; bloqueante en PHP) y devuelve 10 filas sintéticas.
- `cpucompute`: lee `n` de query (default 200); doble loop O(n²) + multiplicación de matrices 64×64 O(C³), devuelve checksum.
- `memalloc`: lee `n` de query (default 20000); construye N objetos anidados vivos a la vez, devuelve agregado + muestra.
- `payload`: recibe `{items:[...100], meta}`, filtra activos, suma y devuelve muestra transformada.

`n` viaja en el `path` del registry (`/cpucompute?n=200`), así se tunea desde `targets.json` sin rebuild.
Cada scenario define su propio perfil de carga (stages/thresholds) en su `.js` — no se reusa el de holamundo.

## Cómo se ejecutan los benchmarks

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

**Qué hace `run_benchmark.sh`:**
1. Resuelve qué targets y scenarios correr (filtros + `enabled` en los registries).
2. `docker compose up -d --build` de los servicios seleccionados.
3. Espera a que cada container esté `healthy` (timeout 90s; si falla, dumpea logs y aborta).
4. Por cada par target×scenario: lanza `docker stats` en background y corre `k6 run` con las env vars.
5. Vuelca el JSON de k6 a `results/<target>_<scenario>_<ts>.json` y los stats a `..._stats.jsonl`.
6. Al final corre `compare_results.py`, que genera `reports/comparison_<ts>.md`
   (tabla ordenada por p95 ascendente, con latencias, throughput, error rate, CPU y memoria).

## Requisitos del host

- Docker + Docker Compose
- k6 (`brew install k6` / `apt install k6` / https://k6.io/docs/get-started/installation/)
- Python 3.10+ (scripts de generación y comparación)
- jq (lo usa el runner bash para leer los registries)

## Resource limits por container

Cada container está limitado a **1 CPU y 512 MB RAM** (definido en el `docker-compose.yml` generado).
Para cambiar los límites, modificar `generate_compose.py` y regenerar — no editar el compose a mano.

## Skills del proyecto

- **add-target** — flujo guiado para agregar un nuevo lenguaje/framework al benchmark.
- **add-scenario** — flujo guiado para agregar un nuevo tipo de prueba k6.

Se invocan automáticamente cuando pedís "agregar un target / framework" o "agregar un scenario / prueba".
