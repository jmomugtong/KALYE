import http from 'k6/http';
import { check, group, sleep } from 'k6';
import {
  getAuthToken,
  randomCoordinate,
  checkResponse,
} from '../utils/helpers.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

/* ------------------------------------------------------------------ */
/*  Options                                                            */
/* ------------------------------------------------------------------ */

export const options = {
  stages: [
    { duration: '1m', target: 50 },    // ramp to 50
    { duration: '2m', target: 100 },   // ramp to 100
    { duration: '2m', target: 200 },   // ramp to 200 – find breaking point
    { duration: '1m', target: 0 },     // ramp down
  ],

  thresholds: {
    http_req_duration: ['p(99)<10000'],  // 99th percentile < 10 s
  },

  tags: {
    testType: 'stress',
  },
};

/* ------------------------------------------------------------------ */
/*  Setup                                                              */
/* ------------------------------------------------------------------ */

export function setup() {
  const token = getAuthToken(BASE_URL);
  return { token };
}

/* ------------------------------------------------------------------ */
/*  Default function                                                   */
/* ------------------------------------------------------------------ */

export default function (data) {
  const authHeaders = {
    headers: {
      Authorization: `Bearer ${data.token}`,
      'Content-Type': 'application/json',
    },
  };

  /* ---------- Health check ---------- */
  group('Health Check', function () {
    const res = http.get(`${BASE_URL}/health`, {
      tags: { name: 'GET /health' },
    });

    checkResponse(res, 200);
  });

  sleep(0.2);

  /* ---------- Nearby detections ---------- */
  group('Nearby Detections', function () {
    const coord = randomCoordinate();
    const url =
      `${BASE_URL}/api/v1/detections/nearby` +
      `?lat=${coord.lat}&lng=${coord.lng}&radius=500`;

    const res = http.get(url, {
      ...authHeaders,
      tags: { name: 'GET /detections/nearby' },
    });

    check(res, {
      'detections: status is not 5xx': (r) => r.status < 500,
    });

    // Track when errors start appearing under load
    if (res.status >= 500) {
      console.warn(
        `Server error at VU ${__VU}, iter ${__ITER}: ` +
        `status=${res.status}, duration=${res.timings.duration}ms`,
      );
    }
  });

  sleep(0.2);

  /* ---------- Walkability analytics ---------- */
  group('Walkability Analytics', function () {
    const res = http.get(
      `${BASE_URL}/api/v1/analytics/walkability/Quezon%20City`,
      {
        ...authHeaders,
        tags: { name: 'GET /analytics/walkability' },
      },
    );

    check(res, {
      'walkability: status is not 5xx': (r) => r.status < 500,
    });

    if (res.status >= 500) {
      console.warn(
        `Server error at VU ${__VU}, iter ${__ITER}: ` +
        `status=${res.status}, duration=${res.timings.duration}ms`,
      );
    }
  });

  sleep(0.5);
}
