import React, { useState, useEffect } from 'react';
import { listInvestigationIntelligence, getIntelligenceDetail, reviewIntelligence, listInvestigationFindings } from '../../../api/investigationIntelligenceApi';
import { Button } from '../../ui/button';
import { AlertCircle, CheckCircle, Eye, ThumbsUp, ThumbsDown, ArrowLeft, RefreshCw, FileText } from 'lucide-react';
import { Search } from 'lucide-react';

export default function IntelligenceTab({ investigationId, canManage }) {
  const [records, setRecords] = useState([]);
  const [findings, setFindings] = useState([]);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [selectedRecordDetail, setSelectedRecordDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [viewMode, setViewMode] = useState('all'); // all, RELEVANT, DISMISSED, PENDING_REVIEW
  const [intelligenceQuery, setIntelligenceQuery] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    loadIntelligence();
  }, [investigationId, viewMode, activeQuery]);

  const handleIntelligenceSearch = (event) => {
    event.preventDefault();
    setActiveQuery(intelligenceQuery);
  };

  const loadIntelligence = async () => {
    setLoading(true);
    setError('');
    try {
      const statusFilter = viewMode !== 'all' ? viewMode : null;
      const data = await listInvestigationIntelligence(investigationId, statusFilter, 0, 50, activeQuery);
      setRecords(data.records || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRecord = async (record) => {
    setSelectedRecord(record);
    setError('');
    try {
      const detail = await getIntelligenceDetail(investigationId, record.raw_record_id);
      setSelectedRecordDetail(detail);
      setReviewNotes(detail.review_notes || '');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleReviewStatus = async (statusVal) => {
    if (!selectedRecord) return;

    setActionLoading(true);
    setError('');
    try {
      await reviewIntelligence(investigationId, selectedRecord.raw_record_id, statusVal, reviewNotes);
      setSuccess(`Intelligence marked as ${statusVal}`);
      setSelectedRecord(null);
      setSelectedRecordDetail(null);
      loadIntelligence();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (selectedRecordDetail) {
    return (
      <div className="space-y-4 font-mono">
        {/* Record Detail Header */}
        <div className="flex items-center justify-between border-b border-border/40 pb-2">
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-sm text-primary uppercase">Intelligence Detail</h3>
            <span className="text-xs text-muted-foreground">[{selectedRecordDetail.raw_record_id}]</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => { setSelectedRecord(null); setSelectedRecordDetail(null); }}
            className="h-7 gap-1 text-xs"
          >
            <ArrowLeft className="w-3 h-3" /> Back
          </Button>
        </div>

        {/* Feedback Banners */}
        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}
        {success && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs rounded flex items-center gap-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />
            {success}
          </div>
        )}

        {/* Record Detail Fields */}
        <div className="p-4 bg-card/40 border border-border/50 rounded space-y-3 text-xs">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5">
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">URL / Source</dt>
              <dd className="text-foreground truncate">{selectedRecordDetail.url || 'N/A'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Fetched At</dt>
              <dd>{selectedRecordDetail.fetched_at ? new Date(selectedRecordDetail.fetched_at).toLocaleString('en-IN') : 'N/A'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Language</dt>
              <dd>{selectedRecordDetail.language || 'N/A'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">AI Relevance</dt>
              <dd>{selectedRecordDetail.relevance_label || 'N/A'} {selectedRecordDetail.relevance_confidence ? `(${selectedRecordDetail.relevance_confidence})` : ''}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-muted-foreground text-[10px] uppercase">Matched Keywords</dt>
              <dd className="text-primary">{selectedRecordDetail.matched_keywords || 'None'}</dd>
            </div>
            {selectedRecordDetail.review_status && (
              <div>
                <dt className="text-muted-foreground text-[10px] uppercase">Current Review Status</dt>
                <dd className={selectedRecordDetail.review_status === 'RELEVANT' ? 'text-green-400 font-bold' : selectedRecordDetail.review_status === 'DISMISSED' ? 'text-red-400 font-bold' : 'text-blue-400'}>
                  [{selectedRecordDetail.review_status}]
                </dd>
              </div>
            )}
            {selectedRecordDetail.reviewed_by_email && (
              <div>
                <dt className="text-muted-foreground text-[10px] uppercase">Reviewed By</dt>
                <dd>{selectedRecordDetail.reviewed_by_email}</dd>
              </div>
            )}
          </dl>

          {/* Cleaned Excerpt */}
          <div className="pt-2 border-t border-border/40">
            <label className="text-[10px] text-muted-foreground uppercase block mb-1">Cleaned Intelligence Excerpt</label>
            <div className="p-3 bg-background border border-border/60 rounded text-[11px] max-h-40 overflow-y-auto whitespace-pre-wrap">
              {selectedRecordDetail.cleaned_text || selectedRecordDetail.raw_text_excerpt || 'No excerpt available.'}
            </div>
          </div>
        </div>

        {/* Investigator Decision Card */}
        {canManage && (
          <div className="p-4 bg-card/60 border border-border/60 rounded space-y-3">
            <h4 className="font-bold text-xs uppercase text-muted-foreground">Investigator Review Decision</h4>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase block mb-1">Review Notes</label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Contextual reasoning for this review decision..."
                className="w-full bg-background border border-border/60 rounded px-2 py-1.5 text-xs h-16 resize-none"
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => handleReviewStatus('RELEVANT')}
                disabled={actionLoading}
                className="flex-1 gap-1 text-xs bg-emerald-600 hover:bg-emerald-700"
              >
                <ThumbsUp className="w-3.5 h-3.5" /> Mark Relevant
              </Button>
              <Button
                size="sm"
                onClick={() => handleReviewStatus('DISMISSED')}
                disabled={actionLoading}
                variant="outline"
                className="flex-1 gap-1 text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
              >
                <ThumbsDown className="w-3.5 h-3.5" /> Dismiss
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 font-mono">
      {/* Header & Filter Controls */}
      <div className="flex items-center justify-between border-b border-border/40 pb-2">
        <h3 className="font-bold text-sm uppercase tracking-wider text-muted-foreground">
          Raw Intelligence Feed
        </h3>
        <Button size="sm" variant="ghost" onClick={loadIntelligence} className="h-6 w-6 p-0 text-xs">
          <RefreshCw className="w-3 h-3" />
        </Button>
      </div>

      <div className="flex gap-1.5 flex-wrap">

              <form onSubmit={handleIntelligenceSearch} className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                  <input
                    value={intelligenceQuery}
                    onChange={(event) => setIntelligenceQuery(event.target.value)}
                    placeholder="Search this investigation by meaning or exact text..."
                    className="w-full bg-background border border-border/60 rounded px-8 py-1.5 text-xs"
                  />
                </div>
                <Button type="submit" size="sm" className="h-8 text-xs">Search</Button>
              </form>
        {['all', 'PENDING_REVIEW', 'RELEVANT', 'DISMISSED'].map((st) => (
          <Button
            key={st}
            size="sm"
            variant={viewMode === st ? 'default' : 'outline'}
            onClick={() => setViewMode(st)}
            className="h-6 text-[11px] px-2.5 uppercase"
          >
            {st === 'all' ? 'All Intelligence' : st}
          </Button>
        ))}
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Intelligence Record List */}
      {loading ? (
        <div className="text-xs text-muted-foreground p-4 text-center animate-pulse">
          Loading intelligence feed...
        </div>
      ) : records.length === 0 ? (
        <div className="text-xs text-muted-foreground p-6 text-center border border-dashed border-border/40 rounded">
          No raw intelligence records found for this investigation. Attach sources and trigger a crawl to populate.
        </div>
      ) : (
        <div className="space-y-2">
          {records.map((record) => (
            <div
              key={record.id}
              onClick={() => handleSelectRecord(record)}
              className="p-3 bg-card/40 border border-border/40 rounded text-xs cursor-pointer hover:border-primary/50 hover:bg-card/60 transition-all flex items-start justify-between gap-3 group"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                  <span className="font-bold truncate text-foreground">{record.source_url || 'No URL'}</span>
                  <span className={`text-[10px] uppercase font-mono ${record.review_status === 'RELEVANT' ? 'text-green-400 font-bold' : record.review_status === 'DISMISSED' ? 'text-red-400 font-bold' : 'text-blue-400'}`}>
                    [{record.review_status || 'PENDING_REVIEW'}]
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground mt-1 flex gap-3">
                  <span>Fetched: {record.fetched_at ? new Date(record.fetched_at).toLocaleDateString('en-IN') : 'N/A'}</span>
                  {record.matched_keywords && <span>Keywords: {record.matched_keywords}</span>}
                  {record.relevance_label && <span>Relevance: {record.relevance_label}</span>}
                </div>
              </div>
              <Eye className="w-4 h-4 text-muted-foreground opacity-60 group-hover:opacity-100 flex-shrink-0" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

