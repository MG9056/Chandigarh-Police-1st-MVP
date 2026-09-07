import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { listInvestigationAlerts, createAlert, resolveAlert } from '../../../api/investigationAlertsApi';
import { Button } from '../../ui/button';
import { useAuth } from '../../../context/AuthContext';
import { AlertCircle, CheckCircle, Plus, RefreshCw, Bell, Filter } from 'lucide-react';

const SEVERITY_COLORS = {
  CRITICAL: 'text-red-400 border-red-700 bg-red-950/60',
  HIGH: 'text-orange-400 border-orange-700 bg-orange-950/60',
  MEDIUM: 'text-yellow-400 border-yellow-700 bg-yellow-950/60',
  LOW: 'text-slate-400 border-slate-600 bg-slate-900/60',
};

const STATUS_COLORS = {
  OPEN: 'text-blue-400',
  ACKNOWLEDGED: 'text-yellow-400',
  RESOLVED: 'text-emerald-400',
};

export default function AlertsTab({ investigationId, canManage }) {
  const { t } = useTranslation();
  const { triggerReAuth } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', severity: 'MEDIUM', description: '' });

  useEffect(() => {
    loadAlerts();
  }, [investigationId, statusFilter]);

  const loadAlerts = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listInvestigationAlerts(investigationId, statusFilter === 'all' ? null : statusFilter);
      setAlerts(data.alerts || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const showSuccessMsg = (msg) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 3500);
  };

  const handleCreate = () => {
    if (!form.title.trim()) { setError('Alert title is required.'); return; }
    triggerReAuth(async () => {
      setActionLoading('create');
      setError('');
      try {
        await createAlert(investigationId, {
          title: form.title.trim(),
          severity: form.severity,
          description: form.description.trim() || undefined,
        });
        showSuccessMsg('Alert created.');
        setForm({ title: '', severity: 'MEDIUM', description: '' });
        setShowCreate(false);
        loadAlerts();
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(null);
      }
    });
  };

  const handleResolve = (alertId) => {
    triggerReAuth(async () => {
      setActionLoading(alertId);
      setError('');
      try {
        await resolveAlert(investigationId, alertId);
        showSuccessMsg('Alert resolved.');
        loadAlerts();
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(null);
      }
    });
  };

  return (
    <div className="space-y-4 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-xs">
          <Bell className="w-3.5 h-3.5 text-yellow-400" />
          <span className="text-muted-foreground">{total} {t('alerts')}</span>
          {['all', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2 py-0.5 rounded border text-[10px] uppercase font-bold transition-colors ${
                statusFilter === s
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'text-muted-foreground border-border hover:border-foreground'
              }`}
            >
              {s === 'all' ? t('All') : s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={loadAlerts} disabled={loading} className="h-7 gap-1 text-xs">
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          {canManage && (
            <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="h-7 gap-1 text-xs">
              <Plus className="w-3 h-3" /> {t('New Alert')}
            </Button>
          )}
        </div>
      </div>

      {/* Create form */}
      {showCreate && canManage && (
        <div className="p-4 bg-card/60 border border-border/60 rounded space-y-2 text-xs">
          <input
            type="text"
            placeholder="Alert title (required)"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
          />
          <select
            value={form.severity}
            onChange={(e) => setForm({ ...form, severity: e.target.value })}
            className="w-full bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
          >
            {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <textarea
            placeholder="Description (optional)"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full bg-background border border-border/60 rounded px-2 py-1.5 text-xs h-16 resize-none"
          />
          <div className="flex gap-2 justify-end">
            <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)} className="text-xs h-7">Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={actionLoading === 'create'} className="text-xs h-7">
              Create Alert
            </Button>
          </div>
        </div>
      )}

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

      {/* Alert List */}
      {loading ? (
        <p className="text-xs text-muted-foreground animate-pulse">{t('Loading alerts...')}</p>
      ) : alerts.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t('No alerts match the selected filter.')}</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => (
            <div key={a.id} className="p-3 bg-card/40 border border-border/50 rounded text-xs space-y-1">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-foreground font-bold">{a.title}</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold uppercase ${SEVERITY_COLORS[a.severity] || ''}`}>
                      {a.severity}
                    </span>
                    <span className={`text-[10px] font-bold uppercase ${STATUS_COLORS[a.status] || ''}`}>
                      {a.status}
                    </span>
                    <span className="text-muted-foreground text-[10px]">
                      {a.created_at ? new Date(a.created_at).toLocaleString('en-IN') : ''}
                    </span>
                  </div>
                  {a.description && (
                    <p className="text-muted-foreground mt-1 text-[10px]">{a.description}</p>
                  )}
                </div>
                {canManage && a.status !== 'RESOLVED' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleResolve(a.id)}
                    disabled={actionLoading === a.id}
                    className="h-6 text-[10px] flex-shrink-0 border-emerald-700 text-emerald-400"
                  >
                    {actionLoading === a.id ? '...' : 'Resolve'}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
