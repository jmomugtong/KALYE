// @ts-nocheck
'use client';

import React, { useState, useCallback } from 'react';
import Map, { Marker, type MapLayerMouseEvent } from 'react-map-gl';

export interface LocationPickerProps {
  onLocationSelect: (lat: number, lng: number) => void;
  initialLocation?: { lat: number; lng: number };
}

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? '';

// Default center: Metro Manila
const DEFAULT_CENTER = { lat: 14.5995, lng: 120.9842 };

export default function LocationPicker({
  onLocationSelect,
  initialLocation,
}: LocationPickerProps) {
  const [marker, setMarker] = useState<{ lat: number; lng: number } | null>(
    initialLocation ?? null,
  );
  const [geoError, setGeoError] = useState<string | null>(null);

  const center = marker ?? initialLocation ?? DEFAULT_CENTER;

  const handleMapClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const { lng, lat } = event.lngLat;
      setMarker({ lat, lng });
      onLocationSelect(lat, lng);
      setGeoError(null);
    },
    [onLocationSelect],
  );

  const handleUseCurrentLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError('Geolocation is not supported by your browser');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setMarker({ lat: latitude, lng: longitude });
        onLocationSelect(latitude, longitude);
        setGeoError(null);
      },
      (err) => {
        setGeoError(`Location access denied: ${err.message}`);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, [onLocationSelect]);

  return (
    <div data-testid="location-picker" className="space-y-2">
      <div className="overflow-hidden rounded-lg border border-gray-200" style={{ height: 250 }}>
        <Map
          initialViewState={{
            longitude: center.lng,
            latitude: center.lat,
            zoom: 13,
          }}
          style={{ width: '100%', height: '100%' }}
          mapStyle="mapbox://styles/mapbox/streets-v12"
          mapboxAccessToken={MAPBOX_TOKEN}
          onClick={handleMapClick}
          cursor="crosshair"
        >
          {marker && (
            <Marker longitude={marker.lng} latitude={marker.lat} color="#3b82f6" />
          )}
        </Map>
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={handleUseCurrentLocation}
          className="inline-flex items-center gap-1.5 rounded-md bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-200"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="3" />
            <line x1="12" y1="2" x2="12" y2="6" />
            <line x1="12" y1="18" x2="12" y2="22" />
            <line x1="2" y1="12" x2="6" y2="12" />
            <line x1="18" y1="12" x2="22" y2="12" />
          </svg>
          Use Current Location
        </button>

        {marker && (
          <span className="text-xs text-gray-500">
            {marker.lat.toFixed(5)}, {marker.lng.toFixed(5)}
          </span>
        )}
      </div>

      {geoError && (
        <p className="text-xs text-red-600">{geoError}</p>
      )}
    </div>
  );
}
