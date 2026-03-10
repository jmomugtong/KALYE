import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import WalkabilityChart from '@/components/Analytics/WalkabilityChart';

// Mock recharts to render testable DOM elements
jest.mock('recharts', () => {
  const OriginalModule = jest.requireActual('recharts');

  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container" style={{ width: 800, height: 400 }}>
        {children}
      </div>
    ),
    BarChart: ({
      children,
      data,
    }: {
      children: React.ReactNode;
      data: Array<{ barangay: string; score: number }>;
    }) => (
      <div data-testid="bar-chart">
        {data.map((entry) => (
          <div key={entry.barangay} data-testid={`bar-${entry.barangay}`}>
            <span data-testid={`label-${entry.barangay}`}>{entry.barangay}</span>
            <span data-testid={`score-${entry.barangay}`}>{entry.score}</span>
          </div>
        ))}
        {children}
      </div>
    ),
    Bar: ({ children, dataKey }: { children: React.ReactNode; dataKey: string }) => (
      <div data-testid={`bar-series-${dataKey}`}>{children}</div>
    ),
    Cell: ({ fill }: { fill: string }) => (
      <div data-testid="bar-cell" data-fill={fill} />
    ),
    XAxis: () => <div data-testid="x-axis" />,
    YAxis: () => <div data-testid="y-axis" />,
    CartesianGrid: () => <div data-testid="cartesian-grid" />,
    Tooltip: () => <div data-testid="tooltip" />,
  };
});

const mockData = [
  { barangay: 'Barangay A', score: 85 },
  { barangay: 'Barangay B', score: 70 },
  { barangay: 'Barangay C', score: 45 },
];

describe('WalkabilityChart', () => {
  it('renders the chart container', () => {
    render(<WalkabilityChart data={mockData} />);
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('renders correct number of bars matching data entries', () => {
    render(<WalkabilityChart data={mockData} />);

    mockData.forEach((entry) => {
      expect(screen.getByTestId(`bar-${entry.barangay}`)).toBeInTheDocument();
      expect(screen.getByTestId(`label-${entry.barangay}`)).toHaveTextContent(
        entry.barangay
      );
      expect(screen.getByTestId(`score-${entry.barangay}`)).toHaveTextContent(
        String(entry.score)
      );
    });
  });

  it('applies correct color coding based on score thresholds', () => {
    render(<WalkabilityChart data={mockData} />);

    const cells = screen.getAllByTestId('bar-cell');
    expect(cells).toHaveLength(3);

    // Score 85 > 80 -> green
    expect(cells[0]).toHaveAttribute('data-fill', '#22c55e');
    // Score 70 >= 60 and <= 80 -> yellow
    expect(cells[1]).toHaveAttribute('data-fill', '#eab308');
    // Score 45 < 60 -> red
    expect(cells[2]).toHaveAttribute('data-fill', '#ef4444');
  });

  it('renders chart axes and grid', () => {
    render(<WalkabilityChart data={mockData} />);
    expect(screen.getByTestId('x-axis')).toBeInTheDocument();
    expect(screen.getByTestId('y-axis')).toBeInTheDocument();
    expect(screen.getByTestId('cartesian-grid')).toBeInTheDocument();
  });

  it('renders tooltip', () => {
    render(<WalkabilityChart data={mockData} />);
    expect(screen.getByTestId('tooltip')).toBeInTheDocument();
  });

  it('handles empty data array', () => {
    render(<WalkabilityChart data={[]} />);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    expect(screen.queryAllByTestId(/^bar-/)).toHaveLength(0);
  });

  it('handles edge case scores at thresholds', () => {
    const edgeData = [
      { barangay: 'Exactly 80', score: 80 },
      { barangay: 'Exactly 60', score: 60 },
      { barangay: 'Just Above 80', score: 81 },
      { barangay: 'Just Below 60', score: 59 },
    ];
    render(<WalkabilityChart data={edgeData} />);
    const cells = screen.getAllByTestId('bar-cell');

    // 80 -> yellow (>80 is green, 80 is not > 80)
    expect(cells[0]).toHaveAttribute('data-fill', '#eab308');
    // 60 -> yellow (>=60)
    expect(cells[1]).toHaveAttribute('data-fill', '#eab308');
    // 81 -> green
    expect(cells[2]).toHaveAttribute('data-fill', '#22c55e');
    // 59 -> red
    expect(cells[3]).toHaveAttribute('data-fill', '#ef4444');
  });
});
