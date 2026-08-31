import { useTranslation } from 'react-i18next';
import { useTheme } from '../theme-provider';
import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import indiaOsmData from '../../assets/india-osm.json';

// Coordinates are real city locations. "intensity" below is a fallback
// used only until real activity data loads (see fetchGeoActivity) —
// once loaded, intensity is derived from real Dread-archive mention
// counts, not hardcoded.
const regionalHotspots = [
  { id: 1, name: 'Chandigarh', regionKey: 'chandigarh', pos: [30.7333, 76.7794], intensity: 'medium' },
  { id: 2, name: 'Ludhiana', regionKey: 'ludhiana', pos: [30.9010, 75.8573], intensity: 'medium' },
  { id: 3, name: 'Amritsar', regionKey: 'amritsar', pos: [31.6340, 74.8723], intensity: 'medium' },
  { id: 4, name: 'Delhi NCR', regionKey: 'delhi_ncr', pos: [28.7041, 77.1025], intensity: 'medium' },
];

function intensityFromShare(share) {
  if (share >= 0.5) return 'critical';
  if (share >= 0.2) return 'high';
  if (share > 0) return 'medium';
  return 'low';
}

const detailedHotspots = [
  // Chandigarh Sub-nodes
  { id: 101, name: 'Sector 17, CHD', pos: [30.7398, 76.7827], intensity: 'high' },
  { id: 102, name: 'Sector 43, CHD', pos: [30.7244, 76.7450], intensity: 'critical' },
  { id: 103, name: 'IT Park, CHD', pos: [30.7275, 76.8437], intensity: 'medium' },
  // Ludhiana Sub-nodes
  { id: 201, name: 'Ferozepur Rd, LDH', pos: [30.8931, 75.8239], intensity: 'high' },
  { id: 202, name: 'Transport Nagar, LDH', pos: [30.9125, 75.8756], intensity: 'critical' },
  // Amritsar Sub-nodes
  { id: 301, name: 'Walled City, ASR', pos: [31.6289, 74.8755], intensity: 'high' },
  { id: 302, name: 'Transit Node, ASR', pos: [31.6410, 74.8510], intensity: 'medium' },
  // Delhi Sub-nodes
  { id: 401, name: 'Connaught Place, DEL', pos: [28.6304, 77.2177], intensity: 'critical' },
  { id: 402, name: 'Dwarka, DEL', pos: [28.5921, 77.0460], intensity: 'high' },
  { id: 403, name: 'Noida Border, NCR', pos: [28.5700, 77.3200], intensity: 'high' },
];

const INTENSITY_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: null, // resolved from theme below
  low: '#64748b',
};

const createPulseIcon = (intensity, theme) => {
  const color = INTENSITY_COLORS[intensity] ?? (theme === 'dark' ? '#84cc16' : '#22c55e');
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `
      <div style="position: relative; width: 16px; height: 16px;">
        <div class="slow-pulse" style="position: absolute; inset: -8px; background-color: ${color}; border-radius: 50%; opacity: 0.4;"></div>
        <div style="position: relative; z-index: 10; width: 16px; height: 16px; background-color: ${color}; border-radius: 50%; box-shadow: 0 0 10px ${color};"></div>
      </div>
    `,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });
};

function MapZoomTracker({ setZoomLevel }) {
  useMapEvents({
    zoomend: (e) => {
      setZoomLevel(e.target.getZoom());
    },
  });
  return null;
}

export default function TrafficHotspots() {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const [zoomLevel, setZoomLevel] = useState(7);
  const [geoActivity, setGeoActivity] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/geo/activity')
      .then(res => res.json())
      .then(setGeoActivity)
      .catch(err => console.error("Error fetching geo activity:", err));
  }, []);

  const tileUrl = theme === 'dark' 
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

  // Regional markers get their intensity from real Dread-archive mention
  // counts once loaded; detailed sub-city markers stay illustrative
  // (neither dataset has sub-city precision).
  const regionalWithRealData = regionalHotspots.map(spot => {
    if (!geoActivity) return spot;
    const share = geoActivity.share[spot.regionKey] ?? 0;
    const count = geoActivity.counts[spot.regionKey] ?? 0;
    return { ...spot, intensity: intensityFromShare(share), realCount: count, realShare: share };
  });

  const currentHotspots = zoomLevel > 8 ? detailedHotspots : regionalWithRealData;

  return (
    <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-black tracking-widest mb-2 uppercase text-foreground">{t('Traffic Hotspots')}</h2>
          <p className="text-muted-foreground font-mono tracking-wider uppercase text-xs mb-2">{t('Live tracking of encrypted traffic relays across regional nodes.')}</p>
          {geoActivity && (
            <p className="text-muted-foreground/70 font-mono tracking-wider text-[10px] max-w-md">
              {t('Marker intensity reflects real city-name/board-activity mention counts from the Dread archive — a volume proxy, not precise geolocation.')}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="font-mono text-xs text-primary uppercase tracking-widest">{t('Zoom Level')}: {zoomLevel}</p>
          <p className="font-mono text-[10px] text-muted-foreground uppercase">{zoomLevel > 8 ? t('Sector-Level Precision') : t('Regional Overview')}</p>
        </div>
      </div>
      
      <div className="flex-1 bracket-border bg-background/20 backdrop-blur-sm relative overflow-hidden flex items-center justify-center p-4">
        <div className="relative w-full h-full min-h-[500px]">
          <MapContainer 
            center={[29.8, 76.2]} 
            zoom={7} 
            style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}
            zoomControl={true}
          >
            <MapZoomTracker setZoomLevel={setZoomLevel} />
            <TileLayer
              attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
              url={tileUrl}
            />

            {/* User-Provided Indian Boundaries Layer */}
            <GeoJSON 
              data={indiaOsmData} 
              style={{
                color: theme === 'dark' ? '#0ea5e9' : '#0284c7', // Professional blue accent
                weight: 1.5,
                fillOpacity: 0 // Removes the polygon overlay completely, leaving only the crisp boundary line
              }} 
            />

            {currentHotspots.map((spot) => (
              <Marker 
                key={spot.id} 
                position={spot.pos} 
                icon={createPulseIcon(spot.intensity, theme)}
              >
                <Popup className="custom-popup">
                  <div className="font-mono text-xs uppercase tracking-widest text-primary mb-1">{t(spot.name) || spot.name}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">{t('Activity')}: <span className="text-foreground">{t(spot.intensity) || spot.intensity}</span></div>
                  {spot.realCount !== undefined && (
                    <div className="font-mono text-[10px] text-muted-foreground mt-1">
                      {t('Real mentions')}: <span className="text-foreground">{spot.realCount}</span> ({Math.round(spot.realShare * 100)}%)
                    </div>
                  )}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}
