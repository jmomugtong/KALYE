import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import type {
  ApiResponse,
  Detection,
  DetectionFilters,
  Image,
  PaginationParams,
  UploadResponse,
  WalkabilityScore,
  BarangayRanking,
} from '@/types/api';
import type { AuthTokens } from '@/types/user';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor to attach JWT token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== 'undefined') {
      const tokensStr = localStorage.getItem('kalye_tokens');
      if (tokensStr) {
        try {
          const tokens: AuthTokens = JSON.parse(tokensStr);
          config.headers.Authorization = `Bearer ${tokens.access_token}`;
        } catch {
          // Invalid token data, ignore
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('kalye_tokens');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth
export async function login(
  email: string,
  password: string
): Promise<AuthTokens> {
  const response = await apiClient.post<AuthTokens>('/api/v1/auth/login', {
    email,
    password,
  });
  return response.data;
}

export async function register(
  name: string,
  email: string,
  password: string
): Promise<AuthTokens> {
  const response = await apiClient.post<AuthTokens>('/api/v1/auth/register', {
    name,
    email,
    password,
  });
  return response.data;
}

// Images
export interface ImageUploadResult {
  image_id: string;
  status: string;
  message: string;
  detections_created: number;
}

export async function uploadImage(
  file: File,
  latitude?: number,
  longitude?: number,
  onProgress?: (progress: number) => void
): Promise<ImageUploadResult> {
  const formData = new FormData();
  formData.append('file', file);
  if (latitude !== undefined) formData.append('latitude', String(latitude));
  if (longitude !== undefined) formData.append('longitude', String(longitude));

  const response = await apiClient.post<ImageUploadResult>(
    '/api/v1/images/upload',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(progress);
        }
      },
    }
  );
  return response.data;
}

// Detections
export async function getDetections(
  filters?: DetectionFilters,
  pagination?: PaginationParams
): Promise<ApiResponse<Detection[]>> {
  const response = await apiClient.get<ApiResponse<Detection[]>>(
    '/api/v1/detections',
    {
      params: {
        ...filters,
        types: filters?.types?.join(','),
        ...pagination,
      },
    }
  );
  return response.data;
}

export async function getNearbyDetections(
  latitude: number,
  longitude: number,
  radiusMeters: number = 500
): Promise<ApiResponse<Detection[]>> {
  const response = await apiClient.get<ApiResponse<Detection[]>>(
    '/api/v1/detections/nearby',
    {
      params: { latitude, longitude, radius: radiusMeters },
    }
  );
  return response.data;
}

// Walkability
export async function getWalkabilityScore(
  barangay: string,
  city?: string
): Promise<WalkabilityScore> {
  const response = await apiClient.get<WalkabilityScore>(
    '/api/v1/walkability/score',
    {
      params: { barangay, city },
    }
  );
  return response.data;
}

export async function getBarangayRankings(
  city?: string,
  limit: number = 20
): Promise<ApiResponse<BarangayRanking[]>> {
  const response = await apiClient.get<ApiResponse<BarangayRanking[]>>(
    '/api/v1/walkability/rankings',
    {
      params: { city, limit },
    }
  );
  return response.data;
}

export { apiClient };
