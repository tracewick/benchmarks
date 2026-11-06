import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Fixed-RPS hold against /work (or REQUEST_PATH) for high-RPS / spool pipeline runs.
 * Pair with WORK_STACK_DEPTH>0 and a larger PHP_FPM_MAX_CHILDREN on the stand.
 */
const RATE = Number(__ENV.RATE || 500);
const DURATION = __ENV.DURATION || "5m";
const PRE_VUS = Number(__ENV.PRE_VUS || 200);
const MAX_VUS = Number(__ENV.MAX_VUS || 2000);
const REQUEST_PATH = __ENV.REQUEST_PATH || "/work";

export const options = {
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  scenarios: {
    hold: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: PRE_VUS,
      maxVUs: MAX_VUS,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
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
  sleep(1);
  return { baseUrl: BASE_URL, path: REQUEST_PATH };
}

export default function (data) {
  const res = http.get(`${data.baseUrl}${data.path}`);
  check(res, {
    "status is 200": (r) => r.status === 200,
    "ok": (r) => {
      try {
        return r.json("ok") === true;
      } catch (e) {
        return false;
      }
    },
  });
}
