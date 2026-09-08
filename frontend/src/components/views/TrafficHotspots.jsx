import { useTranslation } from 'react-i18next';
import { useTheme } from '../theme-provider';
import { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import indiaOsmData from '../../assets/india-osm.json';
import { apiFetch } from '../../lib/apiClient';
import { Button } from '../ui/button';
import { Maximize, Minimize } from 'lucide-react';

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

// Live crawler markers get a distinct diamond/ring treatment (teal) so they
// are never visually confused with the cached demo dataset's pulse dots.
const LIVE_COLOR = '#2dd4bf';
const createLiveIcon = (radius) => {
  const glow = radius + 8;
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `
      <div style="position: relative; width: ${radius}px; height: ${radius}px; transform: rotate(45deg);">
        <div class="slow-pulse" style="position: absolute; inset: -${glow / 2}px; background-color: ${LIVE_COLOR}; opacity: 0.3;"></div>
        <div style="position: relative; z-index: 10; width: ${radius}px; height: ${radius}px; background-color: ${LIVE_COLOR}; border: 2px solid white; box-shadow: 0 0 10px ${LIVE_COLOR};"></div>
      </div>
    `,
    iconSize: [radius, radius],
    iconAnchor: [radius / 2, radius / 2]
  });
};

const LIVE_POLL_INTERVAL_MS = 60000; // matches backend crawler_to_dataset_updater cadence

export default function TrafficHotspots() {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const [geoActivity, setGeoActivity] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [liveGeo, setLiveGeo] = useState({ places: [], record_count: 0 });
  const [liveError, setLiveError] = useState(null);
  const [liveLoading, setLiveLoading] = useState(true);
  const [showLive, setShowLive] = useState(true);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const mapRef = useRef(null);

  // Leaflet sizes its canvas from the container's dimensions at mount time,
  // so whenever the container resizes out-of-band (entering/exiting
  // fullscreen) we need to explicitly tell it to recalculate.
  useEffect(() => {
    if (!mapRef.current) return;
    const id = setTimeout(() => mapRef.current.invalidateSize(), 250);
    return () => clearTimeout(id);
  }, [isExpanded]);

  useEffect(() => {
  apiFetch('/api/geo/activity')
    .then(res => {
      if (res.status === 401) {
        setLoadError('Your session expired. Please log in again.');
        return null;
      }
      return res.ok ? res.json() : null;
    })
    .then(data => {
      if (!data) return;
      if (data.error) setLoadError(data.error);
      setGeoActivity(data);
    })
    .catch(err => {
      console.error("Error fetching geo activity:", err);
      setLoadError(err.message);
    });
}, []);

  // Live crawler geography layer — pulled from /api/global/geography
  // (place mentions resolved from ingested RawRecords) independently of the
  // cached/demo dataset above, refreshed on an interval. Rendered as a
  // separate marker layer rather than merged counts, so the cached demo
  // dataset's numbers are never mixed with live case data.
  useEffect(() => {
    let cancelled = false;

    const fetchLive = () => {
      apiFetch('/api/global/geography?limit_records=500')
        .then(res => {
          if (res.status === 401) {
            if (!cancelled) setLiveError('Your session expired. Please log in again.');
            return null;
          }
          return res.ok ? res.json() : null;
        })
        .then(liveData => {
          if (cancelled) return;
          if (!liveData) {
            setLiveError(prev => prev || 'Failed to load live crawler geography');
            return;
          }
          setLiveError(null);
          setLiveGeo({
            places: Array.isArray(liveData.places) ? liveData.places : [],
            record_count: liveData.record_count || 0,
          });
          setLiveUpdatedAt(new Date());
        })
        .catch(err => {
          if (cancelled) return;
          console.error("Error fetching live crawler geography:", err);
          setLiveError(err.message);
        })
        .finally(() => {
          if (!cancelled) setLiveLoading(false);
        });
    };

    fetchLive();
    const interval = setInterval(fetchLive, LIVE_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const cartoKey = import.meta.env.VITE_CARTO_API_KEY;
  const tileUrl = cartoKey
    ? (theme === 'dark'
        ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${cartoKey}`
        : `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=${cartoKey}`)
    : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const tileAttribution = cartoKey
    ? '&copy; <a href="https://carto.com/">CARTO</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  const places = useMemo(() => {
    if (!geoActivity?.places || !Array.isArray(geoActivity.places)) return [];
    const total = geoActivity.total_mentions || 0;
    if (total <= 0) return [];
    return geoActivity.places
      .filter((p) => Math.round((p.count / total) * 100) > 0)
      .slice(0, 50);
  }, [geoActivity]);

  const maxCount = places.length ? places[0].count : 0;

  const livePlaces = useMemo(() => {
    if (!showLive || !Array.isArray(liveGeo.places)) return [];
    return liveGeo.places.slice(0, 50);
  }, [liveGeo, showLive]);

  const liveMaxCount = livePlaces.length ? livePlaces[0].count : 0;

  const containerClass = isExpanded
    ? "fixed inset-0 z-[100] bg-background p-6 flex flex-col"
    : "h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500";

  return (
    <div className={containerClass}>
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-black tracking-widest mb-2 uppercase text-foreground">{t('Traffic Hotspots')}</h2>
          <p className="text-muted-foreground font-mono tracking-wider uppercase text-xs mb-2">{t('Real place-name mentions scanned from the full Dread forum archive.')}</p>
          <div className="p-2 mb-2 bg-blue-950/60 border border-blue-700/50 rounded text-[10px] text-blue-300 font-mono inline-block max-w-xl">
            <strong>Demo Dataset (Elliptic++ / Dread Archive)</strong> — shown alongside a live crawler layer below.
          </div>
          {geoActivity && !loadError && (
            <p className="text-muted-foreground/70 font-mono tracking-wider text-[10px] max-w-md">
              {t('Marker size/color reflects real mention counts — a volume proxy, not precise geolocation. A vendor writing "ships to Mumbai" is counted under Mumbai regardless of where they actually are.')}
            </p>
          )}
          {loadError && (
            <p className="text-red-500 font-mono tracking-wider text-[10px] max-w-md">{loadError}</p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <Button
              variant={showLive ? 'default' : 'secondary'}
              size="sm"
              className="text-xs font-mono uppercase tracking-wider"
              onClick={() => setShowLive(v => !v)}
              title={t('Toggle the live crawler geography layer on or off')}
            >
              <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${liveError ? 'bg-red-500' : (liveLoading ? 'bg-yellow-500 animate-pulse' : 'bg-teal-400 animate-pulse')}`}></span>
              {t('Live Crawler Layer')}
            </Button>
            <p className="text-[10px] font-mono uppercase tracking-wider">
              {liveError ? (
                <span className="text-red-500">{t('Live layer unavailable')}: {liveError}</span>
              ) : showLive ? (
                <span className="text-teal-400">
                  {liveLoading
                    ? t('Loading live crawler geography…')
                    : `${t('Live')}: ${liveGeo.record_count} ${t('records')} · ${livePlaces.length} ${t('places')}${liveUpdatedAt ? ` · ${t('updated')} ${liveUpdatedAt.toLocaleTimeString()}` : ''}`}
                </span>
              ) : (
                <span className="text-muted-foreground">{t('Live crawler layer hidden')}</span>
              )}
            </p>
          </div>
        </div>
        {geoActivity && !loadError && (
          <div className="text-right font-mono">
            <p className="text-xs text-primary uppercase tracking-widest">{geoActivity.distinct_places_mentioned ?? 0} {t('places found')}</p>
            <p className="text-[10px] text-muted-foreground uppercase">{geoActivity.total_mentions ?? 0} {t('total mentions')}</p>
          </div>
        )}
      </div>

      <div className={`flex-1 bracket-border bg-background/20 backdrop-blur-sm relative overflow-hidden ${isExpanded ? 'p-2' : 'p-4'}`}>
        <div className="relative w-full h-full">
          <Button
            variant="secondary"
            size="icon"
            className="absolute top-3 right-3 z-[1000] w-8 h-8 opacity-80 hover:opacity-100"
            onClick={() => setIsExpanded(v => !v)}
            title={isExpanded ? t('Exit Full Screen') : t('Full Screen')}
          >
            {isExpanded ? <Minimize className="w-4 h-4 text-red-500" /> : <Maximize className="w-4 h-4" />}
          </Button>
          <MapContainer
            ref={mapRef}
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
                      {t('Share of all place mentions')}: <span className="text-foreground" style={{ color: 'black' }}>{geoActivity ? Math.round((spot.count / geoActivity.total_mentions) * 100) : 0}%</span>
                    </div>
                  </Popup>
                </Marker>
              );
            })}

            {livePlaces.map((spot) => {
              const radius = radiusFor(spot.count, liveMaxCount);
              return (
                <Marker
                  key={`live-${spot.name}`}
                  position={[spot.lat, spot.lon]}
                  icon={createLiveIcon(radius)}
                >
                  <Popup className="custom-popup">
                    <div className="font-mono text-xs uppercase tracking-widest text-teal-600 mb-1">{spot.name} · {t('Live')}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {t('Live case mentions')}: <span className="text-foreground">{spot.count}</span>
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {t('From ingested records')}: <span className="text-foreground" style={{ color: 'black' }}>{liveGeo.record_count}</span>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-sm font-mono text-xs">
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500"></div> {t('Demo: Critical')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-orange-500"></div> {t('Demo: High')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-yellow-500"></div> {t('Demo: Medium')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-slate-500"></div> {t('Demo: Low')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-teal-400 rotate-45"></div> {t('Live Crawler Mentions')}</div>
      </div>
    </div>
  );
}