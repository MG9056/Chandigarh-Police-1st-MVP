import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { listInvestigationKeywords, addKeywordToInvestigation, removeKeywordFromInvestigation } from '../../../api/investigationKeywordsApi';
import { Button } from '../../ui/button';
import { useAuth } from '../../../context/AuthContext';
import { AlertCircle, CheckCircle, Plus, Trash2, RefreshCw, Hash } from 'lucide-react';

export default function KeywordsTab({ investigationId, canManage }) {
  const { t } = useTranslation();
  const { triggerReAuth } = useAuth();
  const [keywords, setKeywords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [newKeywordId, setNewKeywordId] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    loadKeywords();
  }, [investigationId]);

  const loadKeywords = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listInvestigationKeywords(investigationId);
      setKeywords(data.keywords || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddKeyword = async () => {
    if (!newKeywordId.trim()) {
      setError('Please enter a keyword ID');
      return;
    }

    triggerReAuth(async () => {
      setActionLoading(true);
      setError('');
      try {
        await addKeywordToInvestigation(investigationId, newKeywordId.trim());
        setSuccess('Case keyword added successfully');
        setNewKeywordId('');
        setShowAddForm(false);
        loadKeywords();
        setTimeout(() => setSuccess(''), 3000);
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(false);
      }
    });
  };

  const handleRemoveKeyword = async (keywordId, keywordText) => {
    if (!window.confirm(`Deactivate keyword "${keywordText || keywordId}" for this case?`)) return;

    triggerReAuth(async () => {
      setActionLoading(true);
      setError('');
      try {
        await removeKeywordFromInvestigation(investigationId, keywordId);
        setSuccess('Case keyword deactivated');
        loadKeywords();
        setTimeout(() => setSuccess(''), 3000);
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(false);
      }
    });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/40 pb-2">
        <h3 className="font-bold text-sm font-mono uppercase tracking-wider text-muted-foreground">
          {t('Case-Specific Keywords')}
        </h3>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={loadKeywords} className="h-6 w-6 p-0 text-xs">
            <RefreshCw className="w-3 h-3" />
          </Button>
          {canManage && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => { setShowAddForm(!showAddForm); setError(''); }}
              className="h-6 gap-1 text-xs"
            >
              <Plus className="w-3 h-3" /> {showAddForm ? t('Cancel') : t('Add Keyword')}
            </Button>
          )}
        </div>
      </div>

      {/* Notifications */}
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

      {/* Add Keyword Form */}
      {showAddForm && canManage && (
        <div className="p-3 bg-card/60 border border-border/60 rounded space-y-2 font-mono">
          <label className="text-[10px] uppercase text-muted-foreground">Global Keyword ID (UUID or ID string)</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newKeywordId}
              onChange={(e) => setNewKeywordId(e.target.value)}
              placeholder="Keyword ID"
              className="flex-1 bg-background border border-border/60 rounded px-2 py-1 text-xs"
              onKeyDown={(e) => e.key === 'Enter' && handleAddKeyword()}
            />
            <Button size="sm" onClick={handleAddKeyword} disabled={actionLoading} className="text-xs">
              Add
            </Button>
          </div>
        </div>
      )}

      {/* Keyword List */}
      {loading ? (
        <div className="text-xs text-muted-foreground font-mono p-4 text-center animate-pulse">
          {t('Loading keywords...')}
        </div>
      ) : keywords.length === 0 ? (
        <div className="text-xs text-muted-foreground font-mono p-6 text-center border border-dashed border-border/40 rounded">
          {t('No case-specific keywords added yet. Keywords guide crawler intelligence filtering.')}
        </div>
      ) : (
        <div className="space-y-1.5 font-mono">
          {keywords.map((kw) => (
            <div
              key={kw.id}
              className="p-2.5 bg-card/40 border border-border/40 rounded text-xs flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <Hash className="w-3.5 h-3.5 text-primary" />
                <div>
                  <div className="font-bold text-foreground">{kw.keyword_text}</div>
                  <div className="text-muted-foreground text-[10px]">
                    ID: {kw.keyword_id} {kw.language ? `• ${kw.language}` : ''}
                  </div>
                </div>
              </div>
              {canManage && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleRemoveKeyword(kw.keyword_id, kw.keyword_text)}
                  disabled={actionLoading}
                  className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

