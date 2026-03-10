'use client';

import { useQuery } from '@tanstack/react-query';
import { getDetections, getNearbyDetections } from '@/lib/api';
import type { DetectionFilters, PaginationParams } from '@/types/api';

export function useDetections(
  filters?: DetectionFilters,
  pagination?: PaginationParams
) {
  return useQuery({
    queryKey: ['detections', filters, pagination],
    queryFn: () => getDetections(filters, pagination),
    staleTime: 60 * 1000,
  });
}

export function useNearbyDetections(
  latitude: number | undefined,
  longitude: number | undefined,
  radiusMeters: number = 500
) {
  return useQuery({
    queryKey: ['detections', 'nearby', latitude, longitude, radiusMeters],
    queryFn: () =>
      getNearbyDetections(latitude!, longitude!, radiusMeters),
    enabled: latitude !== undefined && longitude !== undefined,
    staleTime: 60 * 1000,
  });
}
