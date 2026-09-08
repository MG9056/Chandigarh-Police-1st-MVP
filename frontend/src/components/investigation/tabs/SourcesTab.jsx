import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { listInvestigationSources, attachSource, detachSource, triggerSourceForInvestigation } from '../../../api/investigationSourcesApi';
import { Button } from '../../ui/button';
import { useAuth } from '../../../context/AuthContext';
import { AlertCircle, CheckCircle, Play, Trash2, Plus, RefreshCw } from 'lucide-react';
import { apiFetch } from '../../../lib/apiClient';
import API_BASE_URL from '../../../config/api';

export default function SourcesTab({ investigationId, canManage }) {
  const { t } = useTranslation();
  const { triggerReAuth } = useAuth();
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [attachingSourceId, setAttachingSourceId] = useState('');
  const [showAttachForm, setShowAttachForm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [availableSources, setAvailableSources] = useState([]);
  const [loadingAvailableSources, setLoadingAvailableSources] = useState(false);

  useEffect(() => {
    loadSources();
    loadAvailableSources();
  }, [investigationId]);

  const loadSources = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listInvestigationSources(investigationId);
      setSources(data.sources || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableSources = async () => {
    setLoadingAvailableSources(true);
    try {
      const response = await apiFetch(`${API_BASE_URL}/sources`, {
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error('Failed to load crawler sources');
      }
      const data = await response.json();
      setAvailableSources(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAvailableSources(false);
    }
  };

  const handleAttachSource = async () => {
    if (!attachingSourceId.trim()) {
      setError('Please enter a source ID');
      return;
    }

    setActionLoading(true);
    setError('');
    try {
      await attachSource(investigationId, attachingSourceId.trim());
      setSuccess('Source attached successfully');
      setAttachingSourceId('');
      setShowAttachForm(false);
      loadSources();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDetachSource = async (sourceId, sourceName) => {
    if (!window.confirm(`Detach source "${sourceName || sourceId}" from this investigation?`)) return;

    triggerReAuth(async () => {
      setActionLoading(true);
      setError('');
      try {
        await detachSource(investigationId, sourceId);
        setSuccess('Source detached successfully');
        loadSources();
        setTimeout(() => setSuccess(''), 3000);
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(false);
      }
    });
  };

  const handleTriggerSource = async (sourceId, sourceName) => {
    setActionLoading(true);
    setError('');
    try {
      const res = await triggerSourceForInvestigation(investigationId, sourceId);
      setSuccess(`Crawl run triggered for ${sourceName || sourceId} [Status: ${res.status || 'QUEUED'}]`);
      setTimeout(() => setSuccess(''), 3500);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Tab Sub-Header */}
      <div className="flex items-center justify-between border-b border-border/40 pb-2">
        <h3 className="font-bold text-sm font-mono uppercase tracking-wider text-muted-foreground">
          {t('Attached Crawler Sources')}
        </h3>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={loadSources} className="h-6 w-6 p-0 text-xs">
            <RefreshCw className="w-3 h-3" />
          </Button>
          {canManage && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => { setShowAttachForm(!showAttachForm); setError(''); }}
              className="h-6 gap-1 text-xs"
            >
              <Plus className="w-3 h-3" /> {showAttachForm ? t('Cancel') : t('Attach Source')}
            </Button>
          )}
        </div>
      </div>

      {/* Feedback Notifications */}
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2 font-mono">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs rounded flex items-center gap-2 font-mono">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          {success}
        </div>
      )}

      {/* Attach Source Form */}
      {showAttachForm && canManage && (
        <div className="p-3 bg-card/60 border border-border/60 rounded space-y-2 font-mono">
          <label className="text-[10px] uppercase text-muted-foreground">Crawler Source</label>
          <div className="flex gap-2">
            <select
              value={attachingSourceId}
              onChange={(e) => setAttachingSourceId(e.target.value)}
              className="flex-1 bg-background border border-border/60 rounded px-2 py-1 text-xs"
              disabled={loadingAvailableSources || actionLoading}
            >
              <option value="">
                {loadingAvailableSources ? 'Loading crawler sources...' : 'Select a crawler source'}
              </option>
              {availableSources
                .filter((source) => !sources.some((attached) => attached.source_id === source.id))
                .map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name} ({source.source_type}) — {source.id}
                  </option>
                ))}
            </select>
            <Button size="sm" onClick={handleAttachSource} disabled={actionLoading} className="text-xs">
              Attach
            </Button>
          </div>
          {!loadingAvailableSources && availableSources.length === 0 && (
            <p className="text-[10px] text-muted-foreground">
              No crawler sources are available. Create one from Data Collection first.
            </p>
          )}
        </div>
      )}

      {/* Source List */}
      {loading ? (
        <div className="text-xs text-muted-foreground font-mono p-4 text-center animate-pulse">
          {t('Loading sources...')}
        </div>
      ) : sources.length === 0 ? (
        <div className="text-xs text-muted-foreground font-mono p-6 text-center border border-dashed border-border/40 rounded">
          {t('No sources attached to this investigation yet.')}
          {canManage && (
            <span
              className="text-primary cursor-pointer ml-1 hover:underline"
              onClick={() => setShowAttachForm(true)}
            >
              Attach a source?
            </span>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {sources.map((source) => (
            <div
              key={source.id}
              className="p-3 bg-card/40 border border-border/40 rounded flex items-center justify-between font-mono text-xs"
            >
              <div>
                <div className="font-bold text-foreground">
                  {source.source_name || source.source_id}
                </div>
                <div className="text-muted-foreground text-[10px] mt-0.5">
                  ID: {source.source_id} {source.source_type ? `• Type: ${source.source_type}` : ''}
                </div>
                <div className="text-muted-foreground text-[10px]">
                  Attached by {source.added_by_email || 'Unknown'} on {new Date(source.added_at).toLocaleDateString('en-IN')}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {canManage && (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleTriggerSource(source.source_id, source.source_name)}
                      disabled={actionLoading}
                      className="h-7 gap-1 text-xs text-primary hover:text-primary/90"
                    >
                      <Play className="w-3 h-3" /> Crawl
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDetachSource(source.source_id, source.source_name)}
                      disabled={actionLoading}
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

