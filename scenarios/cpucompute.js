import http from 'k6/http'
import { check } from 'k6'

// CPU-bound: generación de objetos + transformación + algoritmos O(n²) y O(n³).
// Pocos VUs porque cada request satura el CPU; el objetivo es throughput/CPU,
// no latencia (threshold de duración laxo).
export const options = {
  stages: [
    { duration: '10s', target: 20 },
    { duration: '30s', target: 20 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000'],
  },
}

export default function () {
  const url = `${__ENV.TARGET_URL}${__ENV.TEST_PATH}`
  const method = (__ENV.TEST_METHOD || 'GET').toLowerCase()
  const res = http[method](url)
  check(res, { 'status 200': (r) => r.status === 200 })
}
