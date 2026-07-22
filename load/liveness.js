import http from 'k6/http';
import { check } from 'k6';

// Thresholds and target are supplied by `deployctl load` from release/contract.yaml,
// so the pass/fail line lives in the contract rather than in this script.
const BASE_URL = __ENV.BASE_URL;
const TARGET_PATH = __ENV.TARGET_PATH;

export const options = {
  vus: Number(__ENV.VUS),
  duration: __ENV.DURATION,
  thresholds: {
    http_req_failed: [`rate<${__ENV.MAX_ERROR_RATE}`],
    http_req_duration: [`p(95)<${__ENV.MAX_P95_MILLIS}`],
    checks: [`rate>${__ENV.MIN_CHECK_RATE}`],
  },
};

export default function () {
  const response = http.get(`${BASE_URL}${TARGET_PATH}`);
  check(response, {
    'status is 200': (r) => r.status === 200,
  });
}
