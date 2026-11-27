import http from "k6/http";
import { check } from "k6";

export const options = {
  summaryTrendStats: ["med", "p(95)", "p(99)"],
  scenarios: {
    fixed: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.RATE),
      timeUnit: "1s",
      duration: __ENV.DURATION,
      preAllocatedVUs: 10,
      maxVUs: 20,
      gracefulStop: "5s",
    },
  },
  thresholds: {
    checks: ["rate==1"],
    http_req_failed: ["rate==0"],
    dropped_iterations: ["count==0"],
  },
};

export default function () {
  const response = http.get("http://127.0.0.1:18150/work");
  check(response, {
    "response includes fixed work and stable worker PID": (result) =>
      result.status === 200 &&
      result.body === __ENV.EXPECTED &&
      result.headers["X-Worker-Pid"] === __ENV.WORKER_PID,
  });
}
