---
name: add-target
description: Agregar un nuevo target (lenguaje + framework) al benchmark suite de stressing-tools. Usar cuando el usuario pida agregar un target, un nuevo framework, un nuevo lenguaje, o un servidor más para comparar performance. Cubre el registro en config/targets.json, la creación del Dockerfile y servidor mínimo, la regeneración del docker-compose y la validación.
---

# Agregar un target al benchmark

Un "target" es un servidor HTTP mínimo de un lenguaje/framework que se va a benchmarkear contra los demás.

## Invariantes (NO romper)

Todo target nuevo DEBE cumplir:
- Escuchar **internamente en el puerto 3000** (el `port` del registry es solo el mapeo al host, no el de escucha).
- Incluir **`curl`** en la imagen final (lo usa el healthcheck del compose; si falta, el container nunca queda `healthy` y el runner aborta).
- Exponer el/los endpoint(s) declarados en `tests` devolviendo **HTTP 200**.
- `port` host **único** (mirar los ya usados en `config/targets.json`; convención: siguiente libre desde 3008+).
- `name` con convención `<lenguaje>-<framework>` (ej. `go-gin`, `rust-actix`).

## Pasos

### 1. Registrar en `config/targets.json`
Agregar una entrada al array:
```json
{
  "name": "<lenguaje>-<framework>",
  "language": "<lenguaje>",
  "framework": "<framework>",
  "port": <siguiente-port-libre>,
  "enabled": true,
  "tests": {
    "holamundo": { "method": "GET", "path": "/holamundo" }
  }
}
```
Replicar en `tests` los scenarios que el target vaya a soportar (mirar las keys que usan los otros targets). El `path` puede variar por framework (ej. Laravel usa `/api/holamundo`).

### 2. Crear `targets/<name>/`
- Servidor mínimo que responda el endpoint con un JSON tipo `{"mensaje": "hola mundo"}` y escuche en `0.0.0.0:3000`.
- `Dockerfile` que instale dependencias, instale `curl`, exponga 3000 y arranque el server.

Patrones de referencia por lenguaje (copiar el estilo del existente):
- **node** → `targets/node-express/` (alpine + `apk add curl`, `npm install --omit=dev`).
- **python** → `targets/python-fastapi/` (slim + `apt-get install curl`, uvicorn con `--workers`).
- **go** → `targets/go-gin/` (multi-stage: build en `golang:alpine`, runtime en `alpine` + `curl`, binario `CGO_ENABLED=0`).
- **php** → `targets/php-laravel-fpm/` (php-fpm+nginx) o `targets/php-laravel-octane/` (swoole) según el modelo de ejecución.

Para servidores con runtime pesado (Laravel, NestJS) subir `start_period`/`retries` no es necesario manualmente: el generador ya pone `start_period: 30s` y `retries: 15`.

### 3. Regenerar el compose
```bash
python3 scripts/generate_compose.py
```
**Nunca** editar `docker-compose.yml` a mano — se sobrescribe. El healthcheck usa el `path` del scenario `holamundo` (o el primer test si no existe).

### 4. Validar
```bash
./scripts/run_benchmark.sh --targets <name> --scenarios holamundo
```
Verificar que el container quede `healthy`, que k6 corra sin errores 200, y que aparezca en `reports/comparison_<ts>.md`.

Si el container no queda healthy: `docker logs <name> --tail 30` — causa más común es que `curl` falte en la imagen o que el server escuche en un puerto distinto de 3000.

### 5. Actualizar README.md
En la tabla de **Targets** del `README.md` agregar una fila con el nuevo target:
```
| <name>   | <lenguaje> + <framework>   | <port>   | /holamundo   |
```
También actualizar la sección **Estructura del repositorio** si corresponde (ej. el subdirectorio nuevo bajo `targets/`).

### 6. Cerrar
Recordar al usuario commitear: la entrada en `targets.json`, el dir `targets/<name>/`, el `docker-compose.yml` regenerado y el `README.md` actualizado. `results/` está gitignored; `reports/` se commitea.
