import { useTranslation } from 'react-i18next';
import { useTheme } from '../theme-provider';
import { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import indiaOsmData from '../../assets/india-osm.json';

// Marker color/size tiers are computed relative to the mention counts
// actually returned by /api/geo/activity (see tierFor below) — there's
// no fixed absolute scale, since that depends entirely on what's in
// the archive.
const TIER_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#64748b',
};

function tierFor(count, maxCount) {
  if (maxCount <= 0) return 'low';
  const ratio = count / maxCount;
  if (ratio >= 0.5) return 'critical';
  if (ratio >= 0.2) return 'high';
  if (ratio >= 0.05) return 'medium';
  return 'low';
}

function radiusFor(count, maxCount) {
  const minR = 6, maxR = 20;
  if (maxCount <= 0) return minR;
  return Math.round(minR + (maxR - minR) * Math.sqrt(count / maxCount));
}

const createPulseIcon = (tier, radius) => {
  const color = TIER_COLORS[tier];
  const glow = radius + 8;
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `
      <div style="position: relative; width: ${radius}px; height: ${radius}px;">
        <div class="slow-pulse" style="position: absolute; inset: -${glow / 2}px; background-color: ${color}; border-radius: 50%; opacity: 0.35;"></div>
        <div style="position: relative; z-index: 10; width: ${radius}px; height: ${radius}px; background-color: ${color}; border-radius: 50%; box-shadow: 0 0 10px ${color};"></div>
      </div>
    `,
    iconSize: [radius, radius],
    iconAnchor: [radius / 2, radius / 2]
  });
};

export default function TrafficHotspots() {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const [geoActivity, setGeoActivity] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/geo/activity')
      .then(res => res.json())
      .then(data => {
        if (data.error) setLoadError(data.error);
        setGeoActivity(data);
      })
      .catch(err => {
        console.error("Error fetching geo activity:", err);
        setLoadError(err.message);
      });
  }, []);

  // CARTO's raster basemaps now require a free API key or every tile
  // gets an "API KEY REQUIRED" watermark stamped on it (a policy change
  // on their end, not something broken here — see .env for how to get
  // a free key). Falls back to plain OpenStreetMap tiles if no key is
  // configured, which have no watermark but also no dark-theme variant.
  const cartoKey = import.meta.env.VITE_CARTO_API_KEY;
  const tileUrl = cartoKey
    ? (theme === 'dark'
        ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${cartoKey}`
        : `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=${cartoKey}`)
    : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const tileAttribution = cartoKey
    ? '&copy; <a href="https://carto.com/">CARTO</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  // Every place the scan actually found a mention of, capped to the
  // top 50 so the map stays legible — the underlying scan itself is
  // never truncated, only how many markers get drawn.
  const places = useMemo(() => {
    if (!geoActivity?.places) return [];
    return geoActivity.places.slice(0, 50);
  }, [geoActivity]);

  const maxCount = places.length ? places[0].count : 0;

  return (
    <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-black tracking-widest mb-2 uppercase text-foreground">{t('Traffic Hotspots')}</h2>
          <p className="text-muted-foreground font-mono tracking-wider uppercase text-xs mb-2">{t('Real place-name mentions scanned from the full Dread forum archive.')}</p>
          {geoActivity && !loadError && (
            <p className="text-muted-foreground/70 font-mono tracking-wider text-[10px] max-w-md">
              {t('Marker size/color reflects real mention counts — a volume proxy, not precise geolocation. A vendor writing "ships to Mumbai" is counted under Mumbai regardless of where they actually are.')}
            </p>
          )}
          {loadError && (
            <p className="text-red-500 font-mono tracking-wider text-[10px] max-w-md">{loadError}</p>
          )}
        </div>
        {geoActivity && !loadError && (
          <div className="text-right">
            <p className="font-mono text-xs text-primary uppercase tracking-widest">{geoActivity.distinct_places_mentioned} {t('places found')}</p>
            <p className="font-mono text-[10px] text-muted-foreground uppercase">{geoActivity.total_mentions} {t('total mentions')}</p>
          </div>
        )}
      </div>

      <div className="flex-1 bracket-border bg-background/20 backdrop-blur-sm relative overflow-hidden flex items-center justify-center p-4">
        <div className="relative w-full h-full min-h-[500px]">
          <MapContainer
            center={[22.5, 79.0]}
            zoom={5}
            style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}
            zoomControl={true}
          >
            <TileLayer
              attribution={tileAttribution}
              url={tileUrl}
            />

            <GeoJSON
              data={indiaOsmData}
              style={{
                color: theme === 'dark' ? '#0ea5e9' : '#0284c7',
                weight: 1.5,
                fillOpacity: 0
              }}
            />

            {places.map((spot) => {
              const tier = tierFor(spot.count, maxCount);
              const radius = radiusFor(spot.count, maxCount);
              return (
                <Marker
                  key={spot.name}
                  position={[spot.lat, spot.lon]}
                  icon={createPulseIcon(tier, radius)}
                >
                  <Popup className="custom-popup">
                    <div className="font-mono text-xs uppercase tracking-widest text-primary mb-1">{spot.name}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {t('Mentions')}: <span className="text-foreground">{spot.count}</span>
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {t('Share of all place mentions')}: <span className="text-foreground">{geoActivity ? Math.round((spot.count / geoActivity.total_mentions) * 100) : 0}%</span>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}