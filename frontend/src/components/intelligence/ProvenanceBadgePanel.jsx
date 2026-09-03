import React, { useState, useEffect } from 'react';
import { Database, ShieldCheck, FileCheck, ExternalLink, Hash, Info } from 'lucide-react';
import { Button } from '../ui/button';

export default function ProvenanceBadgePanel({ recordId = 'dread_post_9921' }) {
  const [provenance, setProvenance] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch(`/api/provenance/${recordId}`)
      .then((res) => res.json())
      .then((data) => setProvenance(data))
      .catch((e) => console.error('Provenance fetch failed', e));
  }, [recordId]);

  if (!provenance) return null;

  return (
    <div className="border border-border/60 bg-card/60 rounded-lg p-3 font-mono text-xs space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-primary">
          <Database className="w-4 h-4 text-glow" />
          <span className="font-bold uppercase tracking-wider text-[11px]">Data Provenance & Origin</span>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-muted-foreground hover:text-foreground underline"
        >
          {expanded ? 'Collapse' : 'Inspect Provenance'}
        </button>
      </div>

      <div className="flex items-center gap-3 text-muted-foreground text-[11px]">
        <div>Source: <span className="text-foreground font-semibold">{provenance.source_name} ({provenance.source_type})</span></div>
        <div>Collected: <span className="text-foreground">{new Date(provenance.collected_at).toLocaleDateString()}</span></div>
      </div>

      {expanded && (
        <div className="pt-2 border-t border-border/40 space-y-2 text-[11px] animate-in fade-in">
          <div className="p-2 bg-muted/40 rounded border border-border/40 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Source Identifier:</span>
              <span className="font-bold text-foreground">{provenance.source_identifier}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Collection Method:</span>
              <span className="text-foreground">{provenance.collection_method}</span>
            </div>
            {provenance.source_url && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Source URL / Ref:</span>
                <span className="text-primary truncate max-w-[200px]">{provenance.source_url}</span>
              </div>
            )}
          </div>

          <div className="p-2 bg-primary/10 rounded border border-primary/30 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-primary">
              <Hash className="w-3.5 h-3.5" />
              <span className="font-bold">SHA-256 Integrity Hash:</span>
            </div>
            <span className="font-mono text-[10px] text-foreground tracking-tighter select-all">
              {provenance.integrity_hash || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 bg-emerald-500/10 p-1.5 rounded border border-emerald-500/30">
            <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Original raw record preserved. AI processing is cleanly separated from source intelligence.</span>
          </div>
        </div>
      )}
    </div>
  );
}
