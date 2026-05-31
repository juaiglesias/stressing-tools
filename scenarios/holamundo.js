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
  const res = http[method](url)
  check(res, { 'status 200': (r) => r.status === 200 })
}
