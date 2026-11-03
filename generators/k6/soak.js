import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Long soak at fixed arrival rate (METHOD.md soak / RSS growth).
 * Defaults suit a multi-hour run; override RATE / DURATION via env.
 */
const RATE = Number(__ENV.RATE || 10);
const DURATION = __ENV.DURATION || "72h";
const PRE_VUS = Number(__ENV.PRE_VUS || 20);
const MAX_VUS = Number(__ENV.MAX_VUS || 40);

export const options = {
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  scenarios: {
    soak: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: PRE_VUS,
      maxVUs: MAX_VUS,
    },
  },
  // Soft gates: soak cares about survival + growth, not tight latency SLOs.
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
    "profiling on": (r) => {
      try {
        return r.json("profiling_enabled") === true;
      } catch (e) {
        return false;
      }
    },
  });
  sleep(1);
  return { baseUrl: BASE_URL };
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
}
