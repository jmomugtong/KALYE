import http from 'k6/http';
import { check } from 'k6';

/**
 * Authenticate against the KALYE API and return a bearer token.
 *
 * @param {string} baseUrl - The API base URL (e.g. http://localhost:8000).
 * @returns {string} JWT access token.
 */
export function getAuthToken(baseUrl) {
  const payload = JSON.stringify({
    username: __ENV.K6_USERNAME || 'loadtest@kalye.dev',
    password: __ENV.K6_PASSWORD || 'loadtest123',
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'auth_login' },
  };

  const res = http.post(`${baseUrl}/api/v1/auth/login`, payload, params);

  const ok = check(res, {
    'auth: status 200': (r) => r.status === 200,
    'auth: body has access_token': (r) => {
      try {
        return JSON.parse(r.body).access_token !== undefined;
      } catch (_) {
        return false;
      }
    },
  });

  if (!ok) {
    console.error(`Auth failed – status ${res.status}, body: ${res.body}`);
    return '';
  }

  return JSON.parse(res.body).access_token;
}

/**
 * Generate a random coordinate within the Metro Manila bounding box.
 *
 * Latitude  range: 14.4 – 14.8
 * Longitude range: 120.9 – 121.1
 *
 * @returns {{ lat: number, lng: number }}
 */
export function randomCoordinate() {
  const lat = 14.4 + Math.random() * 0.4;   // 14.4 – 14.8
  const lng = 120.9 + Math.random() * 0.2;  // 120.9 – 121.1
  return {
    lat: parseFloat(lat.toFixed(6)),
    lng: parseFloat(lng.toFixed(6)),
  };
}

/**
 * Assert the HTTP response status and log diagnostic info on failure.
 *
 * @param {import('k6/http').RefinedResponse} res - k6 HTTP response object.
 * @param {number} expectedStatus - Expected HTTP status code.
 * @returns {boolean} Whether all checks passed.
 */
export function checkResponse(res, expectedStatus) {
  const passed = check(res, {
    [`status is ${expectedStatus}`]: (r) => r.status === expectedStatus,
    'response body is not empty': (r) => r.body && r.body.length > 0,
  });

  if (!passed) {
    console.error(
      `Request failed – URL: ${res.url}, ` +
      `status: ${res.status} (expected ${expectedStatus}), ` +
      `duration: ${res.timings.duration}ms, ` +
      `body: ${(res.body || '').substring(0, 200)}`
    );
  }

  return passed;
}

/**
 * Generate a minimal 1x1 PNG binary suitable for upload testing.
 *
 * The returned value is a k6-compatible ArrayBuffer that can be passed
 * directly to http.file().
 *
 * @returns {{ data: number[], filename: string, contentType: string }}
 */
export function generateRandomImageUpload() {
  // Minimal valid 1x1 white PNG (68 bytes).
  const png = [
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, // PNG signature
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, // IHDR chunk
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
    0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41, // IDAT chunk
    0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
    0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
    0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, // IEND chunk
    0x44, 0xae, 0x42, 0x60, 0x82,
  ];

  const id = Math.floor(Math.random() * 1e8);

  return {
    data: png,
    filename: `test_image_${id}.png`,
    contentType: 'image/png',
  };
}
