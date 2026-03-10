'use client';

export default function AnalyticsPage() {
  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Walkability scores and detection statistics across barangays
        </p>
      </header>

      {/* Stats overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Images Analyzed', value: '--', description: 'Total processed' },
          { label: 'Detections', value: '--', description: 'Issues found' },
          { label: 'Avg. Walkability', value: '--', description: 'Metro Manila' },
          { label: 'Barangays Covered', value: '--', description: 'Active areas' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-border bg-card p-6"
          >
            <p className="text-sm text-muted-foreground">{stat.label}</p>
            <p className="text-3xl font-bold mt-1">{stat.value}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {stat.description}
            </p>
          </div>
        ))}
      </div>

      {/* Charts placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium mb-4">Detection Distribution</h2>
          <div className="h-64 flex items-center justify-center bg-muted rounded-md">
            <p className="text-sm text-muted-foreground">
              Chart will appear when data is available
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium mb-4">Barangay Rankings</h2>
          <div className="h-64 flex items-center justify-center bg-muted rounded-md">
            <p className="text-sm text-muted-foreground">
              Rankings will appear when data is available
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
