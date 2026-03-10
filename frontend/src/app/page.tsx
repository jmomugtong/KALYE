import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-background to-secondary p-8">
      <div className="max-w-3xl text-center">
        <h1 className="text-6xl font-bold tracking-tight mb-4">
          <span className="text-primary">KALYE</span>
        </h1>
        <p className="text-xl text-muted-foreground mb-2">
          Walkability Intelligence Platform
        </p>
        <h2 className="text-3xl font-semibold mb-6">
          Making Metro Manila Walkable
        </h2>
        <p className="text-lg text-muted-foreground mb-10 max-w-xl mx-auto">
          AI-powered street imagery analysis to detect infrastructure issues,
          score pedestrian safety, and drive urban improvements across barangays.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-md bg-primary px-8 py-3 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 transition-colors"
          >
            Go to Dashboard
          </Link>
          <Link
            href="/dashboard/upload"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-8 py-3 text-sm font-medium shadow-sm hover:bg-accent hover:text-accent-foreground transition-colors"
          >
            Upload Imagery
          </Link>
        </div>
      </div>
    </main>
  );
}
