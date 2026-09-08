import { useEffect, useState, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { forceCollide, forceX, forceY } from 'd3-force';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../theme-provider';
import { ZoomIn, ZoomOut, Maximize, Minimize, Expand, Search, X } from 'lucide-react';
import { Button } from '../ui/button';
import { apiFetch } from '../../lib/apiClient';

const GROUP_ANGLE = {
  suspect: 0,
  wallet: Math.PI / 2,
  account: Math.PI,
  market: (3 * Math.PI) / 2,
  live: Math.PI / 4,
};

const LIVE_POLL_INTERVAL_MS = 60000; // matches backend crawler_to_dataset_updater cadence

// Normalize a /api/global/entities co-occurrence node into the force-graph
// node shape the cached/demo dataset already uses, tagging it as live so it
// can be styled and filtered separately without touching the cached layer.
function normalizeLiveNode(n) {
  return {
    id: n.id,
    label: n.value,
    group: 'live',
    entityType: n.type,
    mentions: n.mentions,
    risk_level: null,
    notes: `Live crawler entity — ${n.mentions} mention${n.mentions === 1 ? '' : 's'} in ingested records`,
    live: true,
  };
}

function normalizeLiveLink(l) {
  return {
    source: l.source,
    target: l.target,
    value: l.weight,
    type: 'live_cooccurrence',
    live: true,
  };
}

export default function NetworkGraph() {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const [source, setSource] = useState('real'); // 'real' | 'synthetic'
  const [data, setData] = useState({ nodes: [], links: [] });
  const [loadError, setLoadError] = useState(null);
  const [liveData, setLiveData] = useState({ nodes: [], links: [], record_count: 0 });
  const [liveError, setLiveError] = useState(null);
  const [liveLoading, setLiveLoading] = useState(true);
  const [showLive, setShowLive] = useState(true);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState(null);
  const containerRef = useRef();
  const fgRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });
  const [isExpanded, setIsExpanded] = useState(false);
  const [hoverNode, setHoverNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchNotFound, setSearchNotFound] = useState(false);

  useEffect(() => {
  setData({ nodes: [], links: [] });
  setLoadError(null);
  const endpoint = source === 'real' ? '/api/network/real' : '/api/network/synthetic';
  apiFetch(endpoint)
    .then(res => {
      if (res.status === 401) {
        setLoadError('Your session expired. Please log in again.');
        return null;
      }
      return res.ok ? res.json() : null;
    })
    .then(graphData => {
      if (!graphData) {
        if (!loadError) setLoadError('Failed to load network data');
        return;
      }
      if (graphData.error) {
        setLoadError(graphData.error);
      }
      setData({
        nodes: Array.isArray(graphData.nodes) ? graphData.nodes : [],
        links: Array.isArray(graphData.links) ? graphData.links : []
      });
    })
    .catch(err => {
      console.error("Error fetching network data:", err);
      setLoadError(err.message);
    });
}, [source]);

  // Live crawler layer — pulled from /api/global/entities (co-occurrence
  // graph built from ingested RawRecords) independently of the cached/demo
  // dataset above, and refreshed on an interval so new crawler output shows
  // up without a page reload. A failure here never blocks the cached graph.
  useEffect(() => {
    let cancelled = false;

    const fetchLive = () => {
      apiFetch('/api/global/entities?limit_records=500')
        .then(res => {
          if (res.status === 401) {
            if (!cancelled) setLiveError('Your session expired. Please log in again.');
            return null;
          }
          return res.ok ? res.json() : null;
        })
        .then(liveGraph => {
          if (cancelled) return;
          if (!liveGraph) {
            setLiveError(prev => prev || 'Failed to load live crawler data');
            return;
          }
          setLiveError(null);
          setLiveData({
            nodes: Array.isArray(liveGraph.nodes) ? liveGraph.nodes : [],
            links: Array.isArray(liveGraph.links) ? liveGraph.links : [],
            record_count: liveGraph.record_count || 0,
          });
          setLiveUpdatedAt(new Date());
        })
        .catch(err => {
          if (cancelled) return;
          console.error("Error fetching live crawler network data:", err);
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

  // Merge the cached/demo dataset with the normalized live crawler layer.
  // Concatenation (not overwrite) is deliberate — the point is to keep
  // rendering whatever is pre-stored/cached while layering live data on top.
  // Collisions are effectively impossible: cached ids come from the
  // synthetic/real_data builders, live ids are "TYPE:VALUE" from the crawler.
  const mergedData = useMemo(() => {
    if (!showLive) return data;
    const liveNodes = liveData.nodes.map(normalizeLiveNode);
    const liveLinks = liveData.links.map(normalizeLiveLink);
    return {
      nodes: [...(data.nodes || []), ...liveNodes],
      links: [...(data.links || []), ...liveLinks],
    };
  }, [data, liveData, showLive]);

  const degreeById = useMemo(() => {
    const m = new Map();
    const links = mergedData?.links || [];
    for (const l of links) {
      const s = typeof l.source === 'object' ? l.source.id : l.source;
      const t = typeof l.target === 'object' ? l.target.id : l.target;
      m.set(s, (m.get(s) || 0) + 1);
      m.set(t, (m.get(t) || 0) + 1);
    }
    return m;
  }, [mergedData]);

  useEffect(() => {
    if (!fgRef.current || !mergedData.nodes || mergedData.nodes.length === 0) return;
    const fg = fgRef.current;
    const degree = (node) => degreeById.get(node.id) || 0;

    fg.d3Force('charge').strength((node) => -60 - 20 * Math.min(degree(node), 10));

    fg.d3Force('link')
      .distance((link) => {
        const base = link.type === 'inferred' ? 130 : (link.type === 'live_cooccurrence' ? 100 : 80);
        const weight = Math.min(link.value || 1, 5);
        return Math.max(30, base - weight * 10);
      })
      .strength((link) => (link.type === 'inferred' ? 0.25 : (link.type === 'live_cooccurrence' ? 0.35 : 0.55)));

    fg.d3Force('collide', forceCollide((node) => 16 + 3 * Math.min(degree(node), 8)));

    fg.d3Force('x', forceX((node) => 220 * Math.cos(GROUP_ANGLE[node.group] ?? 0)).strength(0.05));
    fg.d3Force('y', forceY((node) => 220 * Math.sin(GROUP_ANGLE[node.group] ?? 0)).strength(0.05));

    fg.d3ReheatSimulation();
    setTimeout(() => fg.zoomToFit(800, 60), 900);
  }, [mergedData, degreeById]);

  const highlightNodes = useMemo(() => new Set(), []);
  const highlightLinks = useMemo(() => new Set(), []);

  useEffect(() => {
    highlightNodes.clear();
    highlightLinks.clear();

    if ((hoverNode || selectedNode) && mergedData.links) {
      const activeNode = hoverNode || selectedNode;
      highlightNodes.add(activeNode);
      mergedData.links.forEach(link => {
        if (link.source.id === activeNode.id || link.source === activeNode.id) {
          highlightNodes.add(link.target);
          highlightLinks.add(link);
        }
        if (link.target.id === activeNode.id || link.target === activeNode.id) {
          highlightNodes.add(link.source);
          highlightLinks.add(link);
        }
      });
    }
  }, [hoverNode, selectedNode, mergedData, highlightNodes, highlightLinks]);

  useEffect(() => {
    if (!containerRef.current) return;
    
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height
        });
      }
    });
    
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, [isExpanded]);

  // Zooms/pans the force-graph camera onto the first node whose label (or id,
  // as a fallback for live entities keyed as "TYPE:VALUE") contains the
  // search text, and opens its detail panel like a click would.
  const handleSearch = (e) => {
    e.preventDefault();
    const query = searchQuery.trim().toLowerCase();
    if (!query) return;

    const nodes = mergedData.nodes || [];
    const match = nodes.find((n) => (n.label || '').toLowerCase().includes(query))
      || nodes.find((n) => (n.id || '').toString().toLowerCase().includes(query));

    if (match && fgRef.current && typeof match.x === 'number' && typeof match.y === 'number') {
      setSearchNotFound(false);
      setSelectedNode(match);
      fgRef.current.centerAt(match.x, match.y, 800);
      fgRef.current.zoom(5, 800);
    } else {
      setSearchNotFound(true);
    }
  };

  const clearSearch = () => {
    setSearchQuery('');
    setSearchNotFound(false);
  };

  const containerClass = isExpanded
    ? "fixed inset-0 z-[100] bg-background p-6 flex flex-col"
    : "animate-in fade-in slide-in-from-bottom-4 duration-500 h-full flex flex-col";

  return (
    <div className={containerClass}>
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-black tracking-widest mb-4 uppercase text-foreground">{t('Entity Correlation & Network')}</h2>
          <p className="text-muted-foreground font-mono tracking-wider uppercase text-xs">{t('Interactive map identifying relationships between suspects, wallets, and marketplaces.')}</p>
          <div className="p-2 bg-blue-950/60 border border-blue-700/50 rounded text-[10px] text-blue-300 font-mono inline-block max-w-xl">
            <strong>Demo Dataset (Elliptic++ / Dread Archive)</strong> — layered underneath with live crawler entities.
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex gap-2">
            <Button
              variant={source === 'real' ? 'default' : 'secondary'}
              size="sm"
              className="text-xs font-mono uppercase tracking-wider"
              onClick={() => setSource('real')}
            >
              {t('Real Intelligence')}
            </Button>
            <Button
              variant={source === 'synthetic' ? 'default' : 'secondary'}
              size="sm"
              className="text-xs font-mono uppercase tracking-wider"
              onClick={() => setSource('synthetic')}
            >
              {t('Synthetic Demo')}
            </Button>
            <Button
              variant={showLive ? 'default' : 'secondary'}
              size="sm"
              className="text-xs font-mono uppercase tracking-wider"
              onClick={() => setShowLive(v => !v)}
              title={t('Toggle the live crawler co-occurrence layer on or off')}
            >
              <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${liveError ? 'bg-red-500' : (liveLoading ? 'bg-yellow-500 animate-pulse' : 'bg-teal-400 animate-pulse')}`}></span>
              {t('Live Crawler')}
            </Button>
          </div>
          {source === 'real' && (
            <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider max-w-[280px] text-right">
              {t('Elliptic++ wallet cluster + Dread forum correlation (PGP reuse, replies, wallet mentions).')}
            </p>
          )}
          <p className="text-[10px] font-mono uppercase tracking-wider max-w-[300px] text-right">
            {liveError ? (
              <span className="text-red-500">{t('Live crawler layer unavailable')}: {liveError}</span>
            ) : showLive ? (
              <span className="text-teal-400">
                {liveLoading
                  ? t('Loading live crawler entities…')
                  : `${t('Live')}: ${liveData.record_count} ${t('records')} · ${liveData.nodes.length} ${t('entities')}${liveUpdatedAt ? ` · ${t('updated')} ${liveUpdatedAt.toLocaleTimeString()}` : ''}`}
              </span>
            ) : (
              <span className="text-muted-foreground">{t('Live crawler layer hidden')}</span>
            )}
          </p>
        </div>
      </div>
      <div className="flex-1 flex gap-6 overflow-hidden relative min-h-[500px]">
        <div ref={containerRef} className="flex-1 bracket-border bg-background/20 backdrop-blur-sm overflow-hidden relative h-full">
          <div className="absolute top-4 left-4 z-10 w-60 max-w-[45%]">
            <form
              onSubmit={handleSearch}
              className="flex items-center gap-1.5 bg-background/80 backdrop-blur-md border border-border/50 rounded px-2 py-1.5"
            >
              <Search className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setSearchNotFound(false); }}
                placeholder={t('Search node...')}
                className="bg-transparent border-none outline-none text-xs font-mono w-full placeholder:text-muted-foreground/60"
              />
              {searchQuery && (
                <button type="button" onClick={clearSearch} className="flex-shrink-0 text-muted-foreground hover:text-foreground">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </form>
            {searchNotFound && (
              <p className="mt-1 text-[10px] font-mono text-red-500 uppercase tracking-wider">
                {t('No matching node found')}
              </p>
            )}
          </div>
          <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
            <Button variant="secondary" size="icon" className="w-8 h-8 opacity-80 hover:opacity-100" onClick={() => fgRef.current && fgRef.current.zoom(fgRef.current.zoom() * 1.5, 400)}>
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="icon" className="w-8 h-8 opacity-80 hover:opacity-100" onClick={() => fgRef.current && fgRef.current.zoom(fgRef.current.zoom() / 1.5, 400)}>
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="icon" className="w-8 h-8 opacity-80 hover:opacity-100" onClick={() => fgRef.current && fgRef.current.zoomToFit(400, 50)}>
              <Expand className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="icon" className="w-8 h-8 opacity-80 hover:opacity-100" onClick={() => setIsExpanded(!isExpanded)} title={isExpanded ? t("Exit Full Screen") : t("Full Screen")}>
              {isExpanded ? <Minimize className="w-4 h-4 text-red-500" /> : <Maximize className="w-4 h-4" />}
            </Button>
          </div>
          {mergedData.nodes && mergedData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={fgRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={mergedData}
              nodeRelSize={6}
              linkColor={link => {
                if (highlightLinks.has(link)) return '#ef4444';
                if (link.type === 'inferred') return theme === 'dark' ? '#c084fc' : '#a855f7';
                if (link.type === 'live_cooccurrence') return theme === 'dark' ? '#2dd4bf' : '#0d9488';
                return theme === 'dark' ? '#334155' : '#cbd5e1';
              }}
              linkWidth={link => highlightLinks.has(link) ? 2 : (link.type === 'inferred' || link.type === 'live_cooccurrence' ? 1 : 1.5)}
              linkLineDash={link => link.type === 'inferred' ? [3, 2] : (link.type === 'live_cooccurrence' ? [1, 3] : null)}
              backgroundColor={theme === 'dark' ? 'transparent' : '#f8fafc'}
              onNodeHover={setHoverNode}
              onNodeClick={node => {
                if (selectedNode === node) {
                  setSelectedNode(null);
                } else {
                  setSelectedNode(node);
                }
              }}
              nodeCanvasObject={(node, ctx, globalScale) => {
                const isHighlighted = highlightNodes.has(node) || hoverNode === node || selectedNode === node;
                const isDimmed = (hoverNode || selectedNode) && !isHighlighted;
                
                const fontSize = 12 / globalScale;
                ctx.font = `${fontSize}px Inter, sans-serif`;
                const padding = 6 / globalScale;
                
                let symbol = '';
                let bgColor = '';
                let textColor = '#ffffff';
                
                if (node.group === 'suspect') {
                  symbol = '👤'; 
                  bgColor = '#ef4444'; 
                } else if (node.group === 'wallet') {
                  symbol = '💳'; 
                  bgColor = '#eab308'; 
                  textColor = '#000000';
                } else if (node.group === 'market') {
                  symbol = '🛒'; 
                  bgColor = '#3b82f6'; 
                }  else if (node.group === 'account') {
                  symbol = '🧾';
                  bgColor = '#a855f7';
                } else if (node.group === 'live') {
                  symbol = '📡';
                  bgColor = '#14b8a6';
                }
                else {
                  symbol = '❓';
                  bgColor = '#94a3b8';
                }
                
                const fullText = `${symbol} ${node.label}`;
                const textWidth = ctx.measureText(fullText).width;
                const boxWidth = textWidth + padding * 2;
                const boxHeight = fontSize + padding * 2;
                
                ctx.globalAlpha = isDimmed ? 0.2 : (isHighlighted ? 1 : 0.8);

                ctx.fillStyle = bgColor;
                ctx.beginPath();
                if (ctx.roundRect) {
                  ctx.roundRect(node.x - boxWidth / 2, node.y - boxHeight / 2, boxWidth, boxHeight, 4 / globalScale);
                } else {
                  ctx.rect(node.x - boxWidth / 2, node.y - boxHeight / 2, boxWidth, boxHeight);
                }
                ctx.fill();
                
                ctx.strokeStyle = isHighlighted ? '#ef4444' : (theme === 'dark' ? '#1e293b' : '#cbd5e1');
                ctx.lineWidth = (isHighlighted ? 2 : 1) / globalScale;
                ctx.stroke();

                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = textColor;
                ctx.fillText(fullText, node.x, node.y);
                
                ctx.globalAlpha = 1;
              }}
              nodePointerAreaPaint={(node, color, ctx, globalScale) => {
                const fontSize = 12 / globalScale;
                ctx.font = `${fontSize}px Inter, sans-serif`;
                const padding = 6 / globalScale;
                
                let symbol = '👤';
                if (node.group === 'wallet') symbol = '💳';
                if (node.group === 'market') symbol = '🛒';
                if (node.group === 'account') symbol = '🧾';
                if (node.group === 'live') symbol = '📡';
                
                const fullText = `${symbol} ${node.label}`;
                const textWidth = ctx.measureText(fullText).width;
                const boxWidth = textWidth + padding * 2;
                const boxHeight = fontSize + padding * 2;
                
                ctx.fillStyle = color;
                ctx.beginPath();
                if (ctx.roundRect) {
                  ctx.roundRect(node.x - boxWidth / 2, node.y - boxHeight / 2, boxWidth, boxHeight, 4 / globalScale);
                } else {
                  ctx.rect(node.x - boxWidth / 2, node.y - boxHeight / 2, boxWidth, boxHeight);
                }
                ctx.fill();
              }}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-center px-8 text-muted-foreground animate-pulse font-mono text-xs">
              {loadError ? (
                <span className="text-red-500 font-mono text-xs normal-case animate-none">{loadError}</span>
              ) : (
                t('Loading intelligence network...')
              )}
            </div>
          )}
        </div>
        
        {selectedNode && (
          <div className="w-[350px] flex-shrink-0 bg-background/80 backdrop-blur-md bracket-border p-6 overflow-y-auto animate-in slide-in-from-right-4 duration-300">
            <h3 className="font-bold text-lg mb-6 border-b border-border/50 pb-3 text-primary tracking-widest uppercase font-mono">{t('Intelligence Details')}</h3>
            <div className="space-y-6">
              <div>
                <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Identifier')}</span>
                <p className="font-mono mt-1 text-sm">{selectedNode.label}</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Classification')}</span>
                <p className="mt-1 capitalize">
                  <span className={`px-2 py-1 rounded text-xs font-bold font-mono
                    ${selectedNode.group === 'suspect' ? 'bg-red-500/20 text-red-500' : 
                      selectedNode.group === 'wallet' ? 'bg-yellow-500/20 text-yellow-600 dark:text-yellow-400' : 
                      selectedNode.group === 'live' ? 'bg-teal-500/20 text-teal-500' :
                      'bg-blue-500/20 text-blue-500'}`}>
                    {t(selectedNode.group) || selectedNode.group}
                  </span>
                  {selectedNode.live && (
                    <span className="ml-2 px-2 py-1 rounded text-[10px] font-bold font-mono bg-teal-500/10 text-teal-400 uppercase">
                      {t('Live crawler')}{selectedNode.entityType ? ` · ${selectedNode.entityType}` : ''}
                    </span>
                  )}
                </p>
              </div>
              {selectedNode.live && typeof selectedNode.mentions === 'number' && (
                <div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Mentions in ingested records')}</span>
                  <p className="font-mono mt-1 text-sm">{selectedNode.mentions}</p>
                </div>
              )}
              {selectedNode.risk_level && (
                <div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Risk Level')}</span>
                  <div className="mt-1 flex items-center gap-2">
                    <div className={`h-2 flex-1 rounded-full ${
                      selectedNode.risk_level === 'Critical' ? 'bg-red-700' :
                      selectedNode.risk_level === 'High' ? 'bg-red-500' :
                      selectedNode.risk_level === 'Medium' ? 'bg-yellow-500' :
                      'bg-blue-500'
                    }`}></div>
                    <span className="text-sm font-bold font-mono">{t(selectedNode.risk_level) || selectedNode.risk_level}</span>
                  </div>
                </div>
              )}
              {selectedNode.last_active && (
                <div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Last Active')}</span>
                  <p className="text-sm mt-1 font-mono">{selectedNode.last_active}</p>
                </div>
              )}
              {selectedNode.balance && (
                <div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Estimated Balance')}</span>
                  <p className="font-mono mt-1 text-sm font-semibold">{selectedNode.balance}</p>
                </div>
              )}
              {selectedNode.notes && (
                <div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider font-mono">{t('Notes')}</span>
                  <p className="text-sm mt-1 leading-relaxed text-muted-foreground">{t(selectedNode.notes) || selectedNode.notes}</p>
                </div>
              )}
            </div>
            <Button className="w-full mt-6 bg-secondary hover:bg-secondary/80 text-secondary-foreground font-mono" onClick={() => setSelectedNode(null)}>{t('Close Panel')}</Button>
          </div>
        )}
      </div>
      
      <div className="mt-4 flex flex-wrap gap-4 text-sm font-mono text-xs">
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500"></div> {t('Suspect / Alias')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-yellow-500"></div> {t('Crypto Wallet')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-blue-500"></div> {t('Digital Marketplace')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-purple-500"></div> {t('Account / Handle')}</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-teal-500"></div> {t('Live Crawler Entity')}</div>
        <div className="flex items-center gap-2"><div className="w-6 h-0.5 bg-slate-400"></div> {t('Observed Link')}</div>
        <div className="flex items-center gap-2"><div className="w-6 h-0.5 border-t-2 border-dashed border-slate-400"></div> {t('Inferred Link')}</div>
        <div className="flex items-center gap-2"><div className="w-6 h-0.5 border-t-2 border-dotted border-teal-500"></div> {t('Live Co-occurrence')}</div>
      </div>
    </div>
  );
}