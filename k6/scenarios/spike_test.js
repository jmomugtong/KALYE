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
    { duration: '1s', target: 100 },   // spike: 0 -> 100 instantly
    { duration: '30s', target: 100 },  // sustain 100 users for 30 s
    { duration: '5s', target: 0 },     // cool down
  ],

  thresholds: {
    http_req_duration: ['p(95)<5000'],   // 95th percentile < 5 s
    http_req_failed: ['rate<0.05'],      // error rate < 5 %
  },

  tags: {
    testType: 'spike',
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

  sleep(0.3);

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
      'detections: status 200 or 429': (r) =>
        r.status === 200 || r.status === 429,
      'detections: parseable body': (r) => {
        try {
          JSON.parse(r.body);
          return true;
        } catch (_) {
          return false;
        }
      },
    });
  });

  sleep(0.3);

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
      'walkability: status 200 or 429': (r) =>
        r.status === 200 || r.status === 429,
    });
  });

  sleep(0.5);
}
