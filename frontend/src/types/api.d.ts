import type { DetectionType } from './detection';

export interface Detection {
  id: string;
  imageId: string;
  type: DetectionType;
  confidence: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  latitude: number;
  longitude: number;
  createdAt: string;
  updatedAt: string;
}

export interface Image {
  id: string;
  userId: string;
  url: string;
  thumbnailUrl: string;
  latitude: number;
  longitude: number;
  barangay: string | null;
  city: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  detections: Detection[];
  walkabilityScore: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface WalkabilityScore {
  barangay: string;
  city: string;
  score: number;
  sidewalkCoverage: number;
  obstructionDensity: number;
  adaCompliance: number;
  temporalDecay: number;
  imageCount: number;
  lastUpdated: string;
}

export interface UploadResponse {
  id: string;
  imageUrl: string;
  status: 'pending' | 'processing';
  message: string;
}

export interface DetectionFilters {
  types?: DetectionType[];
  minConfidence?: number;
  barangay?: string;
  city?: string;
  dateFrom?: string;
  dateTo?: string;
}

export interface PaginationParams {
  page: number;
  limit: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  pagination?: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export interface ApiError {
  message: string;
  statusCode: number;
  details?: Record<string, string[]>;
}

export interface BarangayRanking {
  rank: number;
  barangay: string;
  city: string;
  score: number;
  trend: 'up' | 'down' | 'stable';
  change: number;
}
