import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { listInvestigationEvidence } from '../../../api/investigationEvidenceApi';
import { Button } from '../../ui/button';
import { AlertCircle, RefreshCw, ShieldCheck, Database } from 'lucide-react';

export default function EvidenceTab({ investigationId }) {
  const { t } = useTranslation();
  const [evidence, setEvidence] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadEvidence();
  }, [investigationId]);

  const loadEvidence = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listInvestigationEvidence(investigationId);
      setEvidence(data.evidence || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 font-mono">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Database className="w-3.5 h-3.5 text-emerald-400" />
          <span className="font-bold text-foreground">{total}</span> {t('evidence records')}
        </div>
        <Button size="sm" variant="ghost" onClick={loadEvidence} disabled={loading} className="h-7 gap-1 text-xs">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-muted-foreground animate-pulse">{t('Loading evidence...')}</p>
      ) : evidence.length === 0 ? (
        <div className="p-6 text-center text-xs text-muted-foreground border border-border/40 rounded bg-card/30">
          <ShieldCheck className="w-8 h-8 text-muted-foreground/40 mx-auto mb-2" />
          {t('No evidence promoted yet. Mark findings as RELEVANT in the Intelligence or Findings tabs, then promote them here.')}
        </div>
      ) : (
        <div className="space-y-2">
          {evidence.map((e) => (
            <div key={e.id} className="p-3 bg-card/40 border border-border/50 rounded text-xs space-y-1">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-foreground font-bold block">{e.source_name}</span>
                  <span className="text-muted-foreground text-[10px]">
                    {e.source_type} · Evidence #{e.id}
                    {e.finding_id ? ` · Finding #${e.finding_id}` : ''}
                  </span>
                </div>
                {e.promoted_at && (
                  <span className="text-[10px] text-emerald-400 flex-shrink-0">
                    Promoted {new Date(e.promoted_at).toLocaleDateString('en-IN')}
                  </span>
                )}
              </div>
              {e.source_url && (
                <p className="text-[10px] text-blue-400 truncate">{e.source_url}</p>
              )}
              {e.integrity_hash && (
                <p className="text-[10px] text-muted-foreground font-mono truncate">
                  SHA-256: {e.integrity_hash}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
