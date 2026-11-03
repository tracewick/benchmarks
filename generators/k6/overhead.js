import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Fixed-RPS overhead scenario (METHOD.md layer A).
 * Pair with TRACEWICK_ENABLED=0 (baseline) vs 1 + sampleRate 0.1 (on).
 */
const RATE = Number(__ENV.RATE || 20);
const DURATION = __ENV.DURATION || "2m";
const PRE_VUS = Number(__ENV.PRE_VUS || 30);
const MAX_VUS = Number(__ENV.MAX_VUS || 60);

export const options = {
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  scenarios: {
    steady: {
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
    http_req_duration: ["p(95)<1000"],
  },
};

const BASE_URL = (__ENV.BASE_URL || "http://127.0.0.1:8080").replace(/\/$/, "");
const EXPECT_PROFILING = __ENV.EXPECT_PROFILING; // "0" | "1" | unset

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

  if (EXPECT_PROFILING === "0" || EXPECT_PROFILING === "1") {
    const want = EXPECT_PROFILING === "1";
    check(health, {
      "profiling flag matches scenario": (r) => {
        try {
          return r.json("profiling_enabled") === want;
        } catch (e) {
          return false;
        }
      },
    });
  }

  // Short settle so arrival-rate VUs are ready.
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
