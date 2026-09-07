import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../../lib/apiClient';
import { AlertCircle, RefreshCw, Info, MapPin } from 'lucide-react';
import { Button } from '../../ui/button';

// Lazily import leaflet components to avoid SSR issues
let MapContainer, TileLayer, CircleMarker, Popup, L;
try {
  const leaflet = require('react-leaflet');
  MapContainer = leaflet.MapContainer;
  TileLayer = leaflet.TileLayer;
  CircleMarker = leaflet.CircleMarker;
  Popup = leaflet.Popup;
  L = require('leaflet');
  require('leaflet/dist/leaflet.css');
} catch {
  // react-leaflet may not be available in test env
}

const TIER_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#64748b',
};

function tierFor(count, max) {
  if (max <= 0) return 'low';
  const r = count / max;
  if (r >= 0.5) return 'critical';
  if (r >= 0.2) return 'high';
  if (r >= 0.05) return 'medium';
  return 'low';
}

function radiusFor(count, max) {
  const minR = 6, maxR = 20;
  if (max <= 0) return minR;
  return Math.round(minR + (maxR - minR) * Math.sqrt(count / max));
}

export default function GeographyTab({ investigationId }) {
  const [places, setPlaces] = useState([]);
  const [recordCount, setRecordCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadGeography();
  }, [investigationId]);

  const loadGeography = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch(`/api/investigations/${investigationId}/geography`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch geography data');
      }
      const data = await res.json();
      setPlaces(data.places || []);
      setRecordCount(data.record_count || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const maxCount = places.reduce((m, p) => Math.max(m, p.count), 0);

  return (
    <div className="space-y-3 font-mono">
      {/* Banner */}
      <div className="p-2 bg-blue-950/60 border border-blue-700/50 rounded text-[10px] text-blue-300 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
        <span>
          LOCATION entities extracted from <strong>{recordCount}</strong> crawler records,
          resolved against the India Gazetteer. Counts reflect entity mentions —
          not independently verified geolocation signals.
        </span>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          <MapPin className="w-3.5 h-3.5 inline mr-1 text-orange-400" />
          {places.length} resolved locations
        </div>
        <Button size="sm" variant="ghost" onClick={loadGeography} disabled={loading} className="h-7 gap-1 text-xs">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-muted-foreground animate-pulse">Building geography map...</p>
      ) : places.length === 0 ? (
        <div className="p-6 text-center text-xs text-muted-foreground border border-border/40 rounded bg-card/30">
          No geographic data yet. LOCATION entities from crawler records will appear here once the intelligence pipeline runs.
        </div>
      ) : MapContainer ? (
        <div className="rounded overflow-hidden border border-border/40" style={{ height: 380 }}>
          <MapContainer
            center={[22.5, 78.9]}
            zoom={5}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap contributors'
            />
            {places.map((p) => {
              const tier = tierFor(p.count, maxCount);
              const radius = radiusFor(p.count, maxCount);
              return (
                <CircleMarker
                  key={p.name}
                  center={[p.lat, p.lon]}
                  radius={radius}
                  pathOptions={{
                    color: TIER_COLORS[tier],
                    fillColor: TIER_COLORS[tier],
                    fillOpacity: 0.7,
                    weight: 1,
                  }}
                >
                  <Popup>
                    <div className="text-xs font-mono">
                      <strong>{p.name}</strong><br />
                      Mentions: {p.count}<br />
                      Tier: {tier.toUpperCase()}
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      ) : (
        /* Fallback table when leaflet not available */
        <div className="space-y-1">
          {places.slice(0, 20).map((p) => (
            <div key={p.name} className="flex items-center justify-between text-xs bg-card/40 border border-border/40 rounded px-3 py-1.5">
              <span className="text-foreground">{p.name}</span>
              <span className="text-muted-foreground">{p.count} mention{p.count !== 1 ? 's' : ''}</span>
            </div>
          ))}
        </div>
      )}

      {/* Top places table */}
      {places.length > 0 && (
        <div className="text-[10px] text-muted-foreground">
          Top places: {places.slice(0, 5).map((p) => `${p.name} (${p.count})`).join(' · ')}
        </div>
      )}
    </div>
  );
}
