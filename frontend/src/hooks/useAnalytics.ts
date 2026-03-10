import { useQuery } from '@tanstack/react-query';
import {
  fetchWalkabilityScores,
  fetchDetectionStats,
  fetchTrends,
  fetchBarangayRankings,
  fetchStatsSummary,
} from '@/lib/api';
import type {
  AnalyticsFilters,
  WalkabilityScore,
  DetectionStat,
  TrendDataPoint,
  BarangayRanking,
  StatsSummary,
} from '@/types/api';

export function useWalkabilityScores(filters?: AnalyticsFilters) {
  return useQuery<WalkabilityScore[]>({
    queryKey: ['walkabilityScores', filters],
    queryFn: () => fetchWalkabilityScores(filters),
  });
}

export function useDetectionStats(filters?: AnalyticsFilters) {
  return useQuery<DetectionStat[]>({
    queryKey: ['detectionStats', filters],
    queryFn: () => fetchDetectionStats(filters),
  });
}

export function useTrends(filters?: AnalyticsFilters) {
  return useQuery<TrendDataPoint[]>({
    queryKey: ['trends', filters],
    queryFn: () => fetchTrends(filters),
  });
}

export function useBarangayRankings(limit: number = 10) {
  return useQuery<BarangayRanking[]>({
    queryKey: ['barangayRankings', limit],
    queryFn: () => fetchBarangayRankings(limit),
  });
}

export function useStatsSummary(filters?: AnalyticsFilters) {
  return useQuery<StatsSummary>({
    queryKey: ['statsSummary', filters],
    queryFn: () => fetchStatsSummary(filters),
  });
}
