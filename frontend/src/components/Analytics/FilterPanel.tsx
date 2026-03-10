'use client';

import { useState, useCallback } from 'react';
import type { AnalyticsFilters } from '@/types/api';

interface FilterPanelProps {
  onFilterChange: (filters: AnalyticsFilters) => void;
  initialFilters: AnalyticsFilters;
}

const DETECTION_TYPES = [
  { value: 'pothole', label: 'Pothole' },
  { value: 'obstruction', label: 'Obstruction' },
  { value: 'missing_sign', label: 'Missing Sign' },
  { value: 'curb_ramp', label: 'Curb Ramp' },
];

const BARANGAY_OPTIONS = [
  'Barangay 1',
  'Barangay 2',
  'Barangay 3',
  'Barangay 4',
  'Barangay 5',
  'Barangay 6',
  'Barangay 7',
  'Barangay 8',
  'Barangay 9',
  'Barangay 10',
];

function getPresetDateRange(preset: string): { start: string; end: string } {
  const end = new Date();
  const start = new Date();

  switch (preset) {
    case 'last_week':
      start.setDate(end.getDate() - 7);
      break;
    case 'last_month':
      start.setMonth(end.getMonth() - 1);
      break;
    case 'last_year':
      start.setFullYear(end.getFullYear() - 1);
      break;
    default:
      break;
  }

  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

export default function FilterPanel({
  onFilterChange,
  initialFilters,
}: FilterPanelProps) {
  const [filters, setFilters] = useState<AnalyticsFilters>(initialFilters);
  const [barangayDropdownOpen, setBarangayDropdownOpen] = useState(false);

  const handlePresetClick = useCallback(
    (preset: 'last_week' | 'last_month' | 'last_year') => {
      const dateRange = getPresetDateRange(preset);
      setFilters((prev) => ({ ...prev, preset, dateRange }));
    },
    []
  );

  const handleDateChange = useCallback(
    (field: 'start' | 'end', value: string) => {
      setFilters((prev) => ({
        ...prev,
        preset: 'custom',
        dateRange: { ...prev.dateRange, [field]: value },
      }));
    },
    []
  );

  const handleBarangayToggle = useCallback((barangay: string) => {
    setFilters((prev) => {
      const current = prev.barangays;
      const updated = current.includes(barangay)
        ? current.filter((b) => b !== barangay)
        : [...current, barangay];
      return { ...prev, barangays: updated };
    });
  }, []);

  const handleDetectionTypeToggle = useCallback((type: string) => {
    setFilters((prev) => {
      const current = prev.detectionTypes;
      const updated = current.includes(type)
        ? current.filter((t) => t !== type)
        : [...current, type];
      return { ...prev, detectionTypes: updated };
    });
  }, []);

  const handleApply = useCallback(() => {
    onFilterChange(filters);
  }, [filters, onFilterChange]);

  const handleReset = useCallback(() => {
    setFilters(initialFilters);
    onFilterChange(initialFilters);
  }, [initialFilters, onFilterChange]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">Filters</h3>

      {/* Date Range */}
      <div className="mb-5">
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Date Range
        </label>
        <div className="mb-2 flex flex-wrap gap-2">
          {(
            [
              { key: 'last_week', label: 'Last Week' },
              { key: 'last_month', label: 'Last Month' },
              { key: 'last_year', label: 'Last Year' },
            ] as const
          ).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => handlePresetClick(key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                filters.preset === key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={filters.dateRange.start}
            onChange={(e) => handleDateChange('start', e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-500">to</span>
          <input
            type="date"
            value={filters.dateRange.end}
            onChange={(e) => handleDateChange('end', e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Barangay Multi-select */}
      <div className="relative mb-5">
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Barangays
        </label>
        <button
          onClick={() => setBarangayDropdownOpen(!barangayDropdownOpen)}
          className="flex w-full items-center justify-between rounded-md border border-gray-300 bg-white px-3 py-2 text-left text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <span className="text-gray-700">
            {filters.barangays.length === 0
              ? 'All Barangays'
              : `${filters.barangays.length} selected`}
          </span>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={`transition-transform ${barangayDropdownOpen ? 'rotate-180' : ''}`}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        {barangayDropdownOpen && (
          <div className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
            {BARANGAY_OPTIONS.map((barangay) => (
              <label
                key={barangay}
                className="flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={filters.barangays.includes(barangay)}
                  onChange={() => handleBarangayToggle(barangay)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">{barangay}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Detection Type Checkboxes */}
      <div className="mb-5">
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Detection Types
        </label>
        <div className="space-y-2">
          {DETECTION_TYPES.map(({ value, label }) => (
            <label
              key={value}
              className="flex cursor-pointer items-center gap-2"
            >
              <input
                type="checkbox"
                checked={filters.detectionTypes.includes(value)}
                onChange={() => handleDetectionTypeToggle(value)}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">{label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleApply}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Apply
        </button>
        <button
          onClick={handleReset}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
