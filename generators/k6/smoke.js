import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Smoke load against the benchmarks workload.
 * One factor only — see METHOD.md. Default sampleRate on the stand is 1.0 for smoke.
 */
export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || "45s",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1000"],
  },
};

const BASE_URL = (__ENV.BASE_URL || "http://127.0.0.1:8080").replace(/\/$/, "");

export function setup() {
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    "health is 200": (r) => r.status === 200,
    "excimer loaded": (r) => {
      try {
        return r.json("excimer") === true;
      } catch (e) {
        return false;
      }
    },
  });
}

export default function () {
  const res = http.get(`${BASE_URL}/work`);
  check(res, {
    "work status is 200": (r) => r.status === 200,
    "work ok": (r) => {
      try {
        return r.json("ok") === true;
      } catch (e) {
        return false;
      }
    },
  });
  sleep(0.2);
}
