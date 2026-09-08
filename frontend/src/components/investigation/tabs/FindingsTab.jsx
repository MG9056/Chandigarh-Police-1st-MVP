import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { listInvestigationFindings } from '../../../api/investigationFindingsApi';
import { listInvestigationEvidence, promoteToEvidence } from '../../../api/investigationEvidenceApi';
import { Button } from '../../ui/button';
import { AlertCircle, CheckCircle, RefreshCw, ShieldCheck, Filter } from 'lucide-react';

const STATUS_COLORS = {
  RELEVANT: 'text-emerald-400 bg-emerald-950/60 border-emerald-700',
  DISMISSED: 'text-red-400 bg-red-950/60 border-red-700',
  PENDING_REVIEW: 'text-yellow-400 bg-yellow-950/60 border-yellow-700',
};

export default function FindingsTab({ investigationId, canManage }) {
  const { t } = useTranslation();
  const [findings, setFindings] = useState([]);
  const [promotedFindingIds, setPromotedFindingIds] = useState(new Set());
  const [statusFilter, setStatusFilter] = useState('RELEVANT');
  const [loading, setLoading] = useState(true);
  const [promoting, setPromoting] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadData();
  }, [investigationId, statusFilter]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [findingsData, evidenceData] = await Promise.all([
        listInvestigationFindings(investigationId, statusFilter === 'all' ? null : statusFilter),
        listInvestigationEvidence(investigationId),
      ]);
      setFindings(findingsData.findings || []);
      // Build set of already-promoted finding IDs for idempotency UI
      const promoted = new Set(
        (evidenceData.evidence || [])
          .filter(e => e.finding_id != null)
          .map(e => e.finding_id),
      );
      setPromotedFindingIds(promoted);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePromote = async (findingId) => {
    setPromoting(findingId);
    setError('');
    try {
      await promoteToEvidence(investigationId, findingId);
      setSuccess('Finding promoted to evidence successfully.');
      setTimeout(() => setSuccess(''), 3500);
      loadData();
    } catch (err) {
      if (err.message.includes('409') || err.message.toLowerCase().includes('already been promoted')) {
        setSuccess('This finding was already promoted.');
      } else {
        setError(err.message);
      }
    } finally {
      setPromoting(null);
    }
  };

  return (
    <div className="space-y-4 font-mono">
      {/* Header + Filter */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Filter className="w-3.5 h-3.5" />
          <span>{t('Status')}:</span>
          {['all', 'RELEVANT', 'DISMISSED', 'PENDING_REVIEW'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2 py-0.5 rounded border text-[10px] uppercase font-bold transition-colors ${
                statusFilter === s
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'text-muted-foreground border-border hover:border-foreground'
              }`}
            >
              {s === 'all' ? t('All') : s.replace('_', ' ')}
            </button>
          ))}
        </div>
        <Button size="sm" variant="ghost" onClick={loadData} disabled={loading} className="h-7 gap-1 text-xs">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Feedback */}
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs rounded flex items-center gap-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0" /> {success}
        </div>
      )}

      {/* Findings List */}
      {loading ? (
        <p className="text-xs text-muted-foreground animate-pulse">{t('Loading findings...')}</p>
      ) : findings.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t('No findings match the selected filter.')}</p>
      ) : (
        <div className="space-y-2">
          {findings.map((f) => {
            const alreadyPromoted = promotedFindingIds.has(f.id);
            return (
              <div
                key={f.id}
                className="p-3 bg-card/40 border border-border/50 rounded space-y-1.5 text-xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <span className="text-foreground font-bold truncate block">
                      {f.url || `Record ${f.raw_record_id?.slice(0, 12)}...`}
                    </span>
                    <span className="text-muted-foreground text-[10px]">
                      Finding #{f.id} · Reviewed by {f.reviewed_by_email || '—'} ·{' '}
                      {f.reviewed_at ? new Date(f.reviewed_at).toLocaleString('en-IN') : ''}
                    </span>
                    {f.review_notes && (
                      <p className="text-muted-foreground mt-1 text-[10px] italic">"{f.review_notes}"</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`px-2 py-0.5 rounded border text-[10px] font-bold uppercase ${STATUS_COLORS[f.review_status] || ''}`}>
                      {f.review_status?.replace('_', ' ')}
                    </span>
                    {canManage && f.review_status === 'RELEVANT' && (
                      <Button
                        size="sm"
                        variant={alreadyPromoted ? 'ghost' : 'outline'}
                        onClick={() => !alreadyPromoted && handlePromote(f.id)}
                        disabled={alreadyPromoted || promoting === f.id}
                        className={`h-6 gap-1 text-[10px] ${
                          alreadyPromoted
                            ? 'text-emerald-400 cursor-default'
                            : 'border-emerald-700 text-emerald-400 hover:bg-emerald-950/40'
                        }`}
                      >
                        <ShieldCheck className="w-3 h-3" />
                        {alreadyPromoted ? 'Promoted' : promoting === f.id ? '...' : 'Promote'}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
