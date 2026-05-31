import http from 'k6/http'
import { check } from 'k6'

// POST parse+serialize: mide deserialización + validación + serialización del
// round-trip. El body (100 items) es determinístico y se arma una vez por VU.
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

const items = []
for (let i = 0; i < 100; i++) {
  items.push({ id: i, name: `item-${i}`, value: (i * 7) % 100, active: i % 2 === 0 })
}
const body = JSON.stringify({ items, meta: { source: 'k6', ts: 0 } })
const params = { headers: { 'Content-Type': 'application/json' } }

export default function () {
  const url = `${__ENV.TARGET_URL}${__ENV.TEST_PATH}`
  const res = http.post(url, body, params)
  check(res, { 'status 200': (r) => r.status === 200 })
}
