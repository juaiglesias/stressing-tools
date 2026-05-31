---
name: add-scenario
description: Agregar un nuevo scenario (tipo de prueba k6) al benchmark suite de stressing-tools. Usar cuando el usuario pida agregar un scenario, una prueba nueva, un test de carga distinto, o un nuevo endpoint a medir. Cubre el script k6 en scenarios/, el registro en config/scenarios.json, la declaración del test en cada target y la validación.
---

# Agregar un scenario al benchmark

Un "scenario" es un script k6 que define un patrón de carga (ramp de VUs, duración, thresholds) y un tipo de request. El mismo script corre contra todos los targets que lo declaren.

## Invariantes (NO romper)

- El script k6 DEBE leer la URL/método/path desde env vars inyectadas por el runner, no hardcodearlas:
  - `__ENV.TARGET_URL` → base URL del target (`http://localhost:<port>`).
  - `__ENV.TEST_PATH` → path del endpoint (lo define cada target en su `tests`).
  - `__ENV.TEST_METHOD` → método HTTP.
  - `__ENV.TARGET_NAME` → nombre del target (disponible para tags/logs).
- Así un mismo scenario sirve para todos los targets, aunque cada uno exponga el endpoint en un path distinto.

## Pasos

### 1. Crear `scenarios/<nombre>.js`
Plantilla base (tomar `scenarios/holamundo.js` como referencia):
```javascript
import http from 'k6/http'
import { check } from 'k6'

export const options = {
  stages: [
    { duration: '10s', target: 50 },
    { duration: '30s', target: 50 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
  },
}

export default function () {
  const url = `${__ENV.TARGET_URL}${__ENV.TEST_PATH}`
  const method = (__ENV.TEST_METHOD || 'GET').toLowerCase()
  const res = http[method](url)            // para POST con body: http[method](url, JSON.stringify(payload), { headers })
  check(res, { 'status 200': (r) => r.status === 200 })
}
```
Ajustar `stages` (perfil de carga) y `thresholds` según lo que mida el scenario. Para requests con body (POST/PUT) construir el payload y los headers dentro del default function.

### 2. Registrar en `config/scenarios.json`
Agregar al array:
```json
{
  "name": "<nombre>",
  "file": "scenarios/<nombre>.js",
  "description": "<qué mide este scenario>",
  "enabled": true
}
```
El `name` debe coincidir con la key que se use en `tests` de los targets.

### 3. Declarar el test en cada target relevante (`config/targets.json`)
Para cada target que deba correr este scenario, agregar la key dentro de su `tests`:
```json
"tests": {
  "holamundo": { "method": "GET", "path": "/holamundo" },
  "<nombre>":  { "method": "POST", "path": "/<ruta-en-ese-target>" }
}
```
El `path` puede diferir por framework (ej. Laravel prefija `/api`). Si un target no declara el scenario, el runner imprime `SKIP` y lo omite — válido para roll-outs graduales.

Si los targets necesitan exponer un endpoint nuevo para este scenario, hay que agregarlo en el servidor de cada `targets/<name>/` (y rebuildeará solo en el próximo run).

### 4. Validar
```bash
./scripts/run_benchmark.sh --scenarios <nombre>
```
Verificar que corra contra los targets que lo declaran y que aparezca como sección propia en `reports/comparison_<ts>.md`.

### 5. Cerrar
No hace falta regenerar el compose (los scenarios no afectan `docker-compose.yml`). Recordar commitear: `scenarios/<nombre>.js`, el registro en `scenarios.json`, y los cambios en `targets.json`.
