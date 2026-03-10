import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import InteractiveMap from '@/src/components/Map/InteractiveMap';
import type { Detection } from '@/src/types/detection';

/* ------------------------------------------------------------------ */
/*  Mock react-map-gl – Mapbox GL requires WebGL / browser canvas     */
/* ------------------------------------------------------------------ */

let capturedMoveEnd: ((evt: any) => void) | undefined;
let capturedOnClick: (() => void) | undefined;

jest.mock('react-map-gl', () => {
  const MockMap = React.forwardRef(function MockMap(
    props: any,
    ref: React.Ref<any>
  ) {
    capturedMoveEnd = props.onMoveEnd;
    capturedOnClick = props.onClick;

    // Expose a minimal ref API so the component can call mapRef.current
    React.useImperativeHandle(ref, () => ({
      getMap: () => ({
        getBounds: () => ({
          getNorth: () => 14.7,
          getSouth: () => 14.5,
          getEast: () => 121.1,
          getWest: () => 120.9,
        }),
        zoomIn: jest.fn(),
        zoomOut: jest.fn(),
      }),
      flyTo: jest.fn(),
    }));

    return <div data-testid="mock-map">{props.children}</div>;
  });

  const MockMarker = (props: any) => (
    <div data-testid="mock-marker">{props.children}</div>
  );

  const MockPopup = (props: any) => (
    <div data-testid="mock-popup">{props.children}</div>
  );

  const MockSource = (props: any) => (
    <div data-testid="mock-source">{props.children}</div>
  );

  const MockLayer = (props: any) => <div data-testid="mock-layer" />;

  return {
    __esModule: true,
    default: MockMap,
    Map: MockMap,
    Marker: MockMarker,
    Popup: MockPopup,
    Source: MockSource,
    Layer: MockLayer,
  };
});

/* ------------------------------------------------------------------ */
/*  Fixtures                                                           */
/* ------------------------------------------------------------------ */

const SAMPLE_DETECTIONS: Detection[] = [
  {
    id: 'd1',
    type: 'pothole',
    confidence: 0.92,
    latitude: 14.6,
    longitude: 121.0,
    timestamp: '2025-12-01T10:00:00Z',
    description: 'Large pothole on main road',
    barangay: 'Brgy. 1',
  },
  {
    id: 'd2',
    type: 'obstruction',
    confidence: 0.85,
    latitude: 14.61,
    longitude: 121.01,
    timestamp: '2025-12-02T12:00:00Z',
  },
  {
    id: 'd3',
    type: 'missing_sign',
    confidence: 0.78,
    latitude: 14.59,
    longitude: 120.99,
    timestamp: '2025-12-03T14:00:00Z',
  },
];

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('InteractiveMap', () => {
  beforeEach(() => {
    capturedMoveEnd = undefined;
    capturedOnClick = undefined;
  });

  it('renders the map container', () => {
    render(<InteractiveMap />);
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
    expect(screen.getByTestId('mock-map')).toBeInTheDocument();
  });

  it('shows markers when detections are provided', () => {
    render(<InteractiveMap detections={SAMPLE_DETECTIONS} />);
    const markers = screen.getAllByTestId('mock-marker');
    expect(markers).toHaveLength(SAMPLE_DETECTIONS.length);
  });

  it('calls onBoundsChange when map moves', () => {
    jest.useFakeTimers();
    const onBoundsChange = jest.fn();

    render(
      <InteractiveMap
        detections={[]}
        onBoundsChange={onBoundsChange}
      />
    );

    // Simulate the map's onMoveEnd callback
    expect(capturedMoveEnd).toBeDefined();
    capturedMoveEnd!({ viewState: {} });

    // Debounce fires after 300ms
    jest.advanceTimersByTime(300);
    expect(onBoundsChange).toHaveBeenCalledWith({
      north: 14.7,
      south: 14.5,
      east: 121.1,
      west: 120.9,
    });

    jest.useRealTimers();
  });

  it('toggles layer visibility via controls', () => {
    render(<InteractiveMap detections={SAMPLE_DETECTIONS} />);

    // All detection layers enabled by default – 3 markers visible
    expect(screen.getAllByTestId('mock-marker')).toHaveLength(3);

    // Uncheck "Potholes" layer
    const potholeCheckbox = screen.getByLabelText(/Potholes/);
    fireEvent.click(potholeCheckbox);

    // Now only 2 markers (obstruction + missing_sign)
    expect(screen.getAllByTestId('mock-marker')).toHaveLength(2);
  });

  it('renders layer control checkboxes', () => {
    render(<InteractiveMap />);
    expect(screen.getByText('Potholes')).toBeInTheDocument();
    expect(screen.getByText('Obstructions')).toBeInTheDocument();
    expect(screen.getByText('Missing Signs')).toBeInTheDocument();
    expect(screen.getByText('ADA Issues')).toBeInTheDocument();
    expect(screen.getByText('Heatmap')).toBeInTheDocument();
  });

  it('renders zoom control buttons', () => {
    render(<InteractiveMap />);
    expect(screen.getByLabelText('Zoom in')).toBeInTheDocument();
    expect(screen.getByLabelText('Zoom out')).toBeInTheDocument();
  });
});
