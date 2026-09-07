import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../../../lib/apiClient';
import { AlertCircle, RefreshCw, Clock } from 'lucide-react';
import { Button } from '../../ui/button';

const ACTION_COLORS = {
  INVESTIGATION_CREATED: 'text-emerald-400',
  INVESTIGATION_UPDATED: 'text-blue-400',
  INVESTIGATION_CLOSED: 'text-red-400',
  INVESTIGATION_ASSIGNED: 'text-yellow-400',
  INVESTIGATION_ASSIGNMENT_REMOVED: 'text-orange-400',
  EVIDENCE_PROMOTED: 'text-purple-400',
  ALERT_CREATED: 'text-yellow-400',
  ALERT_RESOLVED: 'text-emerald-400',
  ALERT_DELETED: 'text-red-400',
  INVESTIGATION_INTELLIGENCE_REVIEWED: 'text-cyan-400',
  INVESTIGATION_INTELLIGENCE_REVIEWED_UPDATE: 'text-cyan-400',
  DEFAULT: 'text-muted-foreground',
};

export default function ActivityTab({ investigationId }) {
  const { t } = useTranslation();
  const [activity, setActivity] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadActivity();
  }, [investigationId]);

  const loadActivity = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch(`/api/investigations/${investigationId}/activity?limit=100`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch activity');
      }
      const data = await res.json();
      setActivity(data.activity || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3 font-mono">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="w-3.5 h-3.5" />
          <span>{total} {t('activity entries')}</span>
        </div>
        <Button size="sm" variant="ghost" onClick={loadActivity} disabled={loading} className="h-7 gap-1 text-xs">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-muted-foreground animate-pulse">{t('Loading activity...')}</p>
      ) : activity.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t('No activity recorded yet for this investigation.')}</p>
      ) : (
        <div className="relative border-l-2 border-border/40 ml-2 space-y-0">
          {activity.map((entry) => {
            const actionColor = ACTION_COLORS[entry.action] || ACTION_COLORS.DEFAULT;
            return (
              <div key={entry.id} className="relative pl-5 pb-4 group">
                {/* Timeline dot */}
                <span className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-border border-2 border-background group-hover:border-primary transition-colors" />
                <div className="text-[10px] text-muted-foreground mb-0.5">
                  {entry.timestamp
                    ? new Date(entry.timestamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
                    : '—'}
                  {entry.role && (
                    <span className="ml-2 px-1.5 py-0 rounded bg-muted text-[9px] uppercase font-bold text-muted-foreground">
                      {entry.role}
                    </span>
                  )}
                </div>
                <div className={`text-xs font-bold uppercase tracking-wide ${actionColor}`}>
                  {entry.action?.replace(/_/g, ' ')}
                </div>
                <div className="text-[10px] text-muted-foreground">
                  {entry.result} {entry.user_id ? `· user #${entry.user_id}` : ''}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
