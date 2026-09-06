import React, { useState, useEffect, useRef } from 'react';
import { apiFetch } from '../../../lib/apiClient';
import { AlertCircle, RefreshCw, Info } from 'lucide-react';
import { Button } from '../../ui/button';

const NODE_COLORS = {
  PERSON: '#60a5fa',
  CRYPTO_WALLET: '#f59e0b',
  PHONE: '#34d399',
  EMAIL: '#a78bfa',
  LOCATION: '#fb923c',
  GPE: '#fb923c',
  ORGANISATION: '#38bdf8',
  DEFAULT: '#94a3b8',
};

function nodeColor(type) {
  return NODE_COLORS[type?.toUpperCase()] || NODE_COLORS.DEFAULT;
}

export default function NetworkTab({ investigationId }) {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [recordCount, setRecordCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [ForceGraph, setForceGraph] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  // Lazy-load react-force-graph-2d to avoid SSR issues
  useEffect(() => {
    import('react-force-graph-2d').then((mod) => setForceGraph(() => mod.default));
  }, []);

  useEffect(() => {
    loadEntities();
  }, [investigationId]);

  const loadEntities = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch(`/api/investigations/${investigationId}/entities`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch entity graph');
      }
      const data = await res.json();
      setGraphData({ nodes: data.nodes || [], links: data.links || [] });
      setRecordCount(data.record_count || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3 font-mono">
      {/* Demo / Data provenance banner */}
      <div className="p-2 bg-blue-950/60 border border-blue-700/50 rounded text-[10px] text-blue-300 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
        <span>
          <strong>Observational Data</strong> — This network is derived from{' '}
          <strong>{recordCount}</strong> crawler records for this investigation.
          Edges represent <strong>co-occurrence</strong> (entities appeared in the same source
          document) and are NOT confirmed relationships.
        </span>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          {graphData.nodes.length} entities · {graphData.links.length} co-occurrence edges
        </div>
        <Button size="sm" variant="ghost" onClick={loadEntities} disabled={loading} className="h-7 gap-1 text-xs">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-muted-foreground animate-pulse">Building entity graph...</p>
      ) : graphData.nodes.length === 0 ? (
        <div className="p-6 text-center text-xs text-muted-foreground border border-border/40 rounded bg-card/30">
          No entity data yet. Run the crawler against intelligence records assigned to this investigation.
        </div>
      ) : (
        <div className="relative bg-card/30 border border-border/40 rounded overflow-hidden" style={{ height: 400 }}>
          {ForceGraph ? (
            <ForceGraph
              graphData={graphData}
              width={800}
              height={400}
              backgroundColor="transparent"
              nodeLabel={(n) => `${n.type}: ${n.value} (${n.mentions} mention${n.mentions !== 1 ? 's' : ''})`}
              nodeColor={(n) => nodeColor(n.type)}
              nodeRelSize={5}
              linkLabel={(l) => `CO_OCCURRENCE (weight: ${l.weight})`}
              linkColor={() => '#475569'}
              linkWidth={(l) => Math.min(1 + l.weight * 0.5, 4)}
              onNodeClick={setSelectedNode}
            />
          ) : (
            <p className="text-xs text-muted-foreground p-4 animate-pulse">Loading graph renderer...</p>
          )}
        </div>
      )}

      {/* Selected node detail */}
      {selectedNode && (
        <div className="p-3 bg-card/60 border border-primary/40 rounded text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-bold text-primary">{selectedNode.value}</span>
            <button onClick={() => setSelectedNode(null)} className="text-muted-foreground hover:text-foreground text-[10px]">× close</button>
          </div>
          <div className="text-muted-foreground">
            Type: <span className="text-foreground">{selectedNode.type}</span> ·
            Mentions: <span className="text-foreground">{selectedNode.mentions}</span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
        {Object.entries(NODE_COLORS).filter(([k]) => k !== 'DEFAULT').map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
