'use client';

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { DetectionStat } from '@/types/api';

interface DetectionStatsProps {
  stats: DetectionStat[];
}

const DETECTION_COLORS: Record<string, string> = {
  pothole: '#ef4444',
  obstruction: '#f59e0b',
  missing_sign: '#3b82f6',
  curb_ramp: '#8b5cf6',
};

const FALLBACK_COLORS = [
  '#22c55e',
  '#ec4899',
  '#14b8a6',
  '#f97316',
  '#06b6d4',
  '#84cc16',
];

function getColor(type: string, index: number): string {
  return (
    DETECTION_COLORS[type] ||
    FALLBACK_COLORS[index % FALLBACK_COLORS.length]
  );
}

interface LabelProps {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  percentage: number;
}

function renderLabel({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percentage,
}: LabelProps) {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percentage < 5) return null;

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={12}
      fontWeight={600}
    >
      {`${percentage.toFixed(1)}%`}
    </text>
  );
}

interface TooltipPayloadEntry {
  payload: DetectionStat;
  color: string;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}) {
  if (!active || !payload || payload.length === 0) return null;

  const entry = payload[0].payload;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
      <p className="font-semibold capitalize text-gray-900">
        {entry.type.replace('_', ' ')}
      </p>
      <p className="text-sm text-gray-600">
        Count: <span className="font-medium">{entry.count}</span>
      </p>
      <p className="text-sm text-gray-600">
        Percentage: <span className="font-medium">{entry.percentage.toFixed(1)}%</span>
      </p>
    </div>
  );
}

function formatLegend(value: string): string {
  return value
    .replace('_', ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DetectionStats({ stats }: DetectionStatsProps) {
  return (
    <div className="h-[400px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={stats}
            dataKey="count"
            nameKey="type"
            cx="50%"
            cy="50%"
            outerRadius={140}
            label={renderLabel}
            labelLine={false}
          >
            {stats.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={getColor(entry.type, index)}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend formatter={formatLegend} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
