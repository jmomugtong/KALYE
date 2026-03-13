'use client';

const STATS = [
  { label: 'Images Analyzed', value: '1,247', description: 'Total processed', trend: '+23 today' },
  { label: 'Detections', value: '3,891', description: 'Issues found', trend: '+156 this week' },
  { label: 'Avg. Walkability', value: '54.2', description: 'Metro Manila', trend: '+2.1 vs last month' },
  { label: 'Barangays Covered', value: '142', description: 'Active areas', trend: '/ 1,710 total' },
];

const DISTRIBUTION = [
  { type: 'Potholes', count: 1420, pct: 36.5, color: '#ef4444' },
  { type: 'Obstructions', count: 987, pct: 25.4, color: '#f59e0b' },
  { type: 'Missing Signs', count: 834, pct: 21.4, color: '#8b5cf6' },
  { type: 'Curb Ramp Issues', count: 650, pct: 16.7, color: '#3b82f6' },
];

const RANKINGS = [
  { rank: 1, barangay: 'Legazpi Village', city: 'Makati', score: 82.4, change: +1.2 },
  { rank: 2, barangay: 'Salcedo Village', city: 'Makati', score: 79.1, change: +0.8 },
  { rank: 3, barangay: 'Rockwell Center', city: 'Makati', score: 76.8, change: -0.3 },
  { rank: 4, barangay: 'Bonifacio Global City', city: 'Taguig', score: 75.2, change: +2.1 },
  { rank: 5, barangay: 'Eastwood City', city: 'Quezon City', score: 71.6, change: +0.5 },
  { rank: 6, barangay: 'Ortigas Center', city: 'Pasig', score: 68.3, change: -1.1 },
  { rank: 7, barangay: 'Poblacion', city: 'Makati', score: 64.9, change: +3.4 },
  { rank: 8, barangay: 'Kapitolyo', city: 'Pasig', score: 61.2, change: +1.7 },
];

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
        {STATS.map((stat) => (
          <div key={stat.label} className="rounded-lg border border-border bg-card p-6">
            <p className="text-sm text-muted-foreground">{stat.label}</p>
            <p className="text-3xl font-bold mt-1">{stat.value}</p>
            <p className="text-xs text-green-600 mt-1">{stat.trend}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Detection Distribution */}
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium mb-4">Detection Distribution</h2>
          <div className="space-y-4">
            {DISTRIBUTION.map((item) => (
              <div key={item.type}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">{item.type}</span>
                  <span className="text-muted-foreground">{item.count} ({item.pct}%)</span>
                </div>
                <div className="h-3 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${item.pct}%`, backgroundColor: item.color }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-border text-sm text-muted-foreground">
            Total: <span className="font-semibold text-foreground">3,891</span> detections across{' '}
            <span className="font-semibold text-foreground">142</span> barangays
          </div>
        </div>

        {/* Barangay Rankings */}
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-medium mb-4">Barangay Rankings</h2>
          <div className="space-y-2">
            {RANKINGS.map((r) => (
              <div
                key={r.rank}
                className="flex items-center gap-3 rounded-md px-3 py-2.5 hover:bg-accent/50 transition-colors"
              >
                <span className={`text-sm font-bold w-6 text-center ${
                  r.rank <= 3 ? 'text-primary' : 'text-muted-foreground'
                }`}>
                  {r.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{r.barangay}</p>
                  <p className="text-xs text-muted-foreground">{r.city}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold">{r.score}</p>
                  <p className={`text-xs ${r.change >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                    {r.change >= 0 ? '+' : ''}{r.change}
                  </p>
                </div>
                <div className="w-16">
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${r.score}%`,
                        backgroundColor: r.score >= 70 ? '#22c55e' : r.score >= 40 ? '#eab308' : '#ef4444',
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Temporal trend */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-medium mb-4">Weekly Detection Trend</h2>
        <div className="flex items-end gap-2 h-40">
          {[45, 62, 38, 71, 55, 89, 67, 94, 78, 103, 85, 112].map((val, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-primary/80 hover:bg-primary transition-colors"
                style={{ height: `${(val / 112) * 100}%` }}
              />
              <span className="text-[9px] text-muted-foreground">
                {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][i]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
