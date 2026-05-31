# stressing-tools

Benchmark suite para **comparar la performance de distintos lenguajes y frameworks bajo carga HTTP**.

Cada target es un servidor HTTP mínimo, dockerizado y limitado a los mismos recursos
(**1 CPU / 512 MB**), de modo que las mediciones reflejen el costo real del runtime/framework
y no diferencias de hardware. La carga se genera con [k6](https://k6.io/), que corre en el
**host** (no en Docker) para no contaminar las mediciones con el overhead del contenedor de carga.

El resultado es una tabla comparativa en Markdown con latencia (p50/p95/p99), throughput,
error rate, y uso de CPU y memoria (pico/promedio) por target.

## Targets

`config/targets.json` es la única fuente de verdad de los targets.

| target              | lenguaje | framework      | port host | endpoint        |
|---------------------|----------|----------------|-----------|-----------------|
| node-express        | node     | express        | 3001      | /holamundo      |
| node-fastify        | node     | fastify        | 3002      | /holamundo      |
| node-nestjs         | node     | nestjs         | 3003      | /holamundo      |
| php-laravel         | php      | laravel        | 3004      | /api/holamundo  |
| python-fastapi      | python   | fastapi        | 3005      | /holamundo      |
| php-laravel-octane  | php      | laravel-octane | 3006      | /api/holamundo  |
| php-laravel-fpm     | php      | laravel-fpm    | 3007      | /api/holamundo  |
| go-gin              | go       | gin            | 3008      | /holamundo      |

**Invariantes de todo target:**
- Escucha internamente en el puerto **3000** (el port del registry es solo el mapeo al host).
- La imagen incluye `curl` (lo usa el healthcheck del compose).
- Expone al menos el endpoint del scenario `holamundo` devolviendo HTTP 200.

## Scenarios

`config/scenarios.json` es la única fuente de verdad de los scenarios.

| scenario  | archivo                | descripción                                            |
|-----------|------------------------|--------------------------------------------------------|
| holamundo | scenarios/holamundo.js | GET básico sin I/O, mide throughput puro del framework |

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

scenarios/
  holamundo.js       ← GET básico sin I/O, 50 VUs, ramp 10s + 30s sostenido + 10s down

scripts/
  generate_compose.py  ← genera docker-compose.yml desde targets.json
  run_benchmark.sh     ← orquestador principal (levanta containers, corre k6, compara)
  compare_results.py   ← genera tabla comparativa Markdown desde el JSON de k6

docker-compose.yml   ← GENERADO desde targets.json — no editar a mano
results/             ← gitignored, NDJSON de k6 + JSONL de docker stats
reports/             ← commiteados, tablas comparativas en Markdown
```

## Resource limits por container

Cada container está limitado a **1 CPU y 512 MB RAM** (definido en el `docker-compose.yml`
generado). Para cambiar los límites, modificar `scripts/generate_compose.py` y regenerar —
no editar el compose a mano.

## Extender el benchmark

El proyecto incluye dos skills de Claude Code que guían el flujo:

- **add-target** — agregar un nuevo lenguaje/framework al benchmark.
- **add-scenario** — agregar un nuevo tipo de prueba k6.
