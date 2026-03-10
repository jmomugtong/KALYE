'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { WalkabilityScore } from '@/types/api';

interface WalkabilityChartProps {
  data: Pick<WalkabilityScore, 'barangay' | 'score'>[];
}

function getBarColor(score: number): string {
  if (score > 80) return '#22c55e';
  if (score >= 60) return '#eab308';
  return '#ef4444';
}

interface TooltipPayloadEntry {
  payload: Pick<WalkabilityScore, 'barangay' | 'score'>;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const entry = payload[0].payload;
  const score = entry.score;
  let rating: string;
  let ratingColor: string;

  if (score > 80) {
    rating = 'Good';
    ratingColor = '#22c55e';
  } else if (score >= 60) {
    rating = 'Fair';
    ratingColor = '#eab308';
  } else {
    rating = 'Poor';
    ratingColor = '#ef4444';
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
      <p className="mb-1 font-semibold text-gray-900">{label}</p>
      <p className="text-sm text-gray-600">
        Score: <span className="font-medium">{score}/100</span>
      </p>
      <p className="text-sm" style={{ color: ratingColor }}>
        Rating: {rating}
      </p>
    </div>
  );
}

export default function WalkabilityChart({ data }: WalkabilityChartProps) {
  return (
    <div className="h-[400px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="barangay"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: '#6b7280' }}
            label={{
              value: 'Walkability Score',
              angle: -90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fill: '#374151' },
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="score" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getBarColor(entry.score)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
