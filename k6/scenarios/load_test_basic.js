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
    { duration: '10s', target: 10 },   // ramp up 0 -> 10 users
    { duration: '30s', target: 10 },   // sustain 10 users
    { duration: '10s', target: 0 },    // ramp down 10 -> 0
  ],

  thresholds: {
    http_req_duration: ['p(95)<2000'],   // 95th percentile < 2 s
    http_req_failed: ['rate<0.01'],      // error rate < 1 %
  },

  tags: {
    testType: 'load_basic',
  },
};

/* ------------------------------------------------------------------ */
/*  Setup – authenticate once and share the token                      */
/* ------------------------------------------------------------------ */

export function setup() {
  const token = getAuthToken(BASE_URL);
  return { token };
}

/* ------------------------------------------------------------------ */
/*  Default function – virtual-user loop                               */
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

  sleep(0.5);

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
      'detections: status 200': (r) => r.status === 200,
      'detections: body is JSON array or object': (r) => {
        try {
          JSON.parse(r.body);
          return true;
        } catch (_) {
          return false;
        }
      },
    });
  });

  sleep(0.5);

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
      'walkability: status 200': (r) => r.status === 200,
      'walkability: has score field': (r) => {
        try {
          return JSON.parse(r.body).score !== undefined;
        } catch (_) {
          return false;
        }
      },
    });
  });

  sleep(1);
}
