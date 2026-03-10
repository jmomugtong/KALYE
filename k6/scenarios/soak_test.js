import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import {
  getAuthToken,
  randomCoordinate,
  checkResponse,
} from '../utils/helpers.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

/* ------------------------------------------------------------------ */
/*  Custom metrics – track response times over the soak window to      */
/*  detect memory leaks or gradual degradation.                        */
/* ------------------------------------------------------------------ */

const healthDuration = new Trend('health_duration', true);
const detectionsDuration = new Trend('detections_duration', true);
const walkabilityDuration = new Trend('walkability_duration', true);

/* ------------------------------------------------------------------ */
/*  Options                                                            */
/* ------------------------------------------------------------------ */

export const options = {
  stages: [
    { duration: '30s', target: 50 },    // ramp up
    { duration: '10m', target: 50 },    // sustain for 10 minutes
    { duration: '30s', target: 0 },     // ramp down
  ],

  thresholds: {
    http_req_duration: ['p(95)<3000'],       // 95th percentile < 3 s
    health_duration: ['p(95)<1000'],         // health endpoint stays fast
    detections_duration: ['p(95)<3000'],      // detections stays within budget
    walkability_duration: ['p(95)<3000'],     // walkability stays within budget
  },

  tags: {
    testType: 'soak',
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
    healthDuration.add(res.timings.duration);
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
    });

    detectionsDuration.add(res.timings.duration);
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
    });

    walkabilityDuration.add(res.timings.duration);
  });

  sleep(1);
}

/* ------------------------------------------------------------------ */
/*  Teardown – summarise soak observations                             */
/* ------------------------------------------------------------------ */

export function teardown(data) {
  console.log('Soak test complete. Review custom trend metrics');
  console.log('(health_duration, detections_duration, walkability_duration)');
  console.log('for signs of gradual response-time increase (memory leak indicator).');
}
