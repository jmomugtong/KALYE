'use client';

export default function DashboardPage() {
  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-border px-6 py-4">
        <h1 className="text-2xl font-semibold">Map Overview</h1>
        <p className="text-sm text-muted-foreground">
          Explore walkability scores and detections across Metro Manila
        </p>
      </header>

      <div className="flex-1 relative">
        {/* Map placeholder */}
        <div className="absolute inset-0 flex items-center justify-center bg-muted">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
              <svg
                className="w-8 h-8 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                />
              </svg>
            </div>
            <div>
              <p className="text-lg font-medium">Mapbox Map</p>
              <p className="text-sm text-muted-foreground">
                Set your NEXT_PUBLIC_MAPBOX_TOKEN to enable the interactive map
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Score legend */}
      <div className="border-t border-border px-6 py-3 flex items-center gap-6 text-sm">
        <span className="font-medium">Walkability Score:</span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-score-high" />
          High (70-100)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-score-medium" />
          Medium (40-69)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-score-low" />
          Low (0-39)
        </span>
      </div>
    </div>
  );
}
