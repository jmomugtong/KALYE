'use client';

import { useState } from 'react';
import type { BarangayRanking } from '@/types/api';

interface BarangayRankingsProps {
  rankings: BarangayRanking[];
}

function getScoreColor(score: number): string {
  if (score > 80) return 'text-green-600';
  if (score >= 60) return 'text-yellow-600';
  return 'text-red-600';
}

function getScoreBg(score: number): string {
  if (score > 80) return 'bg-green-50';
  if (score >= 60) return 'bg-yellow-50';
  return 'bg-red-50';
}

function TrendIndicator({
  trend,
  change,
}: {
  trend: 'up' | 'down' | 'stable';
  change: number;
}) {
  if (trend === 'up') {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-medium text-green-600">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 15l-6-6-6 6" />
        </svg>
        +{change.toFixed(1)}
      </span>
    );
  }

  if (trend === 'down') {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-medium text-red-600">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
        -{Math.abs(change).toFixed(1)}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-gray-500">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M5 12h14" />
      </svg>
      0.0
    </span>
  );
}

export default function BarangayRankings({ rankings }: BarangayRankingsProps) {
  const [activeTab, setActiveTab] = useState<'top' | 'bottom'>('top');

  const sorted = [...rankings].sort((a, b) =>
    activeTab === 'top' ? b.score - a.score : a.score - b.score
  );
  const displayed = sorted.slice(0, 10);

  return (
    <div className="w-full">
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setActiveTab('top')}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'top'
              ? 'bg-green-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Top 10
        </button>
        <button
          onClick={() => setActiveTab('bottom')}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'bottom'
              ? 'bg-red-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Bottom 10
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Rank
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Barangay
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Score
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Trend
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {displayed.map((item, index) => (
              <tr key={item.barangay} className="hover:bg-gray-50">
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  {activeTab === 'top'
                    ? index + 1
                    : rankings.length - index}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                  {item.barangay}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-0.5 text-sm font-semibold ${getScoreColor(item.score)} ${getScoreBg(item.score)}`}
                  >
                    {item.score}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <TrendIndicator trend={item.trend} change={item.change} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
