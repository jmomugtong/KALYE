import axios from 'axios';
import type {
  WalkabilityScore,
  BarangayRanking,
  TrendDataPoint,
  DetectionStat,
  StatsSummary,
  AnalyticsFilters,
} from '@/types/api';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function fetchWalkabilityScores(
  filters?: AnalyticsFilters
): Promise<WalkabilityScore[]> {
  const { data } = await api.get('/analytics/walkability', { params: filters });
  return data;
}

export async function fetchDetectionStats(
  filters?: AnalyticsFilters
): Promise<DetectionStat[]> {
  const { data } = await api.get('/analytics/detections/stats', {
    params: filters,
  });
  return data;
}

export async function fetchTrends(
  filters?: AnalyticsFilters
): Promise<TrendDataPoint[]> {
  const { data } = await api.get('/analytics/trends', { params: filters });
  return data;
}

export async function fetchBarangayRankings(
  limit: number = 10
): Promise<BarangayRanking[]> {
  const { data } = await api.get('/analytics/rankings', {
    params: { limit },
  });
  return data;
}

export async function fetchStatsSummary(
  filters?: AnalyticsFilters
): Promise<StatsSummary> {
  const { data } = await api.get('/analytics/summary', { params: filters });
  return data;
}

export default api;
