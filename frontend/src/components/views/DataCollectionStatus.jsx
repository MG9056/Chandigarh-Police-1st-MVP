import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Server,
  Database,
  Globe,
  RefreshCcw,
  MessageSquare,
  Radio,
  Play,
  Square,
  Plus,
  Tag,
  ShieldCheck,
  Activity,
  FileText,
  Trash2,
  Edit3,
  Hash,
  Eye,
  X,
  Search,
  Sparkles,
} from 'lucide-react';
import { Button } from '../ui/button';
import { apiFetch } from '../../lib/apiClient';
import { useAuth } from '../../context/AuthContext';

export default function DataCollectionStatus() {
  const { t } = useTranslation();
  const { triggerReAuth } = useAuth();
  const [activeTab, setActiveTab] = useState('sources'); // 'sources' | 'keywords' | 'activity' | 'raw_records'

  // Data states
  const [sources, setSources] = useState([]);
  const [keywordsData, setKeywordsData] = useState({ active_terms: [], global_keywords: [] });
  const [activity, setActivity] = useState({ items: [], total: 0 });
  const [rawRecords, setRawRecords] = useState({ items: [], total: 0 });

  // UI / Modal states
  const [loading, setLoading] = useState(true);
  const [triggeringId, setTriggeringId] = useState(null);
  const [stoppingId, setStoppingId] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showAddSourceModal, setShowAddSourceModal] = useState(false);
  const [showEditSourceModal, setShowEditSourceModal] = useState(false);
  const [showAddKeywordModal, setShowAddKeywordModal] = useState(false);
  const [actionError, setActionError] = useState('');

  // Form states
  const [newSource, setNewSource] = useState({
    name: '',
    source_type: 'DIRECT_SEED',
    seed_urls: '',
    poll_interval_seconds: 60,
    crawl_delay_seconds: 1.0,
    transport_type: 'direct',
  });
  const [editingSource, setEditingSource] = useState(null);
  const [newKeyword, setNewKeyword] = useState({
    term: '',
    language: 'en',
    category: 'substance',
  });
  const [caseIdInput, setCaseIdInput] = useState('');

  // Fetch Sources
  const fetchSources = async () => {
    try {
      const res = await apiFetch('/api/sources');
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch (err) {
      console.error('Error fetching sources:', err);
    }
  };

  // Fetch Keywords
  const fetchKeywords = async () => {
    try {
      const url = caseIdInput ? `/api/keywords?case_id=${encodeURIComponent(caseIdInput)}` : '/api/keywords';
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setKeywordsData(data);
      }
    } catch (err) {
      console.error('Error fetching keywords:', err);
    }
  };

  // Fetch Activity Feed
  const fetchActivity = async () => {
    try {
      const res = await apiFetch('/api/crawler/activity?page=1&page_size=20');
      if (res.ok) {
        const data = await res.json();
        setActivity(data);
      }
    } catch (err) {
      console.error('Error fetching crawler activity:', err);
    }
  };

  // Fetch Raw Records
  const fetchRawRecords = async () => {
    try {
      const res = await apiFetch('/api/raw-records?status=pending_mapping&limit=30');
      if (res.ok) {
        const data = await res.json();
        setRawRecords(data);
      }
    } catch (err) {
      console.error('Error fetching raw records:', err);
    }
  };

  const reloadAllData = async () => {
    setLoading(true);
    setActionError('');
    await Promise.all([fetchSources(), fetchKeywords(), fetchActivity(), fetchRawRecords()]);
    setLoading(false);
  };

  useEffect(() => {
    reloadAllData();
  }, []);

  useEffect(() => {
  const intervalId = setInterval(() => {
    Promise.all([
      fetchSources(),
      fetchActivity(),
      fetchRawRecords(),
    ]).catch((err) => {
      console.error('Error polling crawler state:', err);
    });
  }, 2000);

  return () => clearInterval(intervalId);
}, []);

  // Trigger Source Run
  const handleTriggerRun = async (sourceId) => {
    setTriggeringId(sourceId);
    setActionError('');
    try {
      const res = await apiFetch(`/api/sources/${sourceId}/trigger`, { method: 'POST' });
      if (res.ok) {
        await Promise.all([fetchSources(), fetchActivity(), fetchRawRecords()]);
      } else {
        const errData = await res.json().catch(() => ({}));
        setActionError(errData.detail || 'Failed to trigger crawler run');
      }
    } catch (err) {
      console.error('Error triggering crawl run:', err);
      setActionError('Network error while triggering crawler run');
    } finally {
      setTriggeringId(null);
    }
  };

  // Stop Source Run
  const handleStopSource = async (sourceId) => {
    setStoppingId(sourceId);
    setActionError('');
    try {
      const res = await apiFetch(`/api/sources/${sourceId}/stop`, { method: 'POST' });
      if (res.ok) {
        await Promise.all([fetchSources(), fetchActivity()]);
      } else {
        const errData = await res.json().catch(() => ({}));
        setActionError(errData.detail || 'Failed to stop crawler target');
      }
    } catch (err) {
      console.error('Error stopping source:', err);
    } finally {
      setStoppingId(null);
    }
  };

  // Delete Source with Password Re-Authentication
  const handleDeleteSource = (sourceId, sourceName) => {
    triggerReAuth(async () => {
      setActionError('');
      try {
        const res = await apiFetch(`/api/sources/${sourceId}`, { method: 'DELETE' });
        if (res.ok) {
          fetchSources();
          fetchActivity();
        } else {
          const errData = await res.json().catch(() => ({}));
          setActionError(errData.detail || 'Failed to delete crawler target');
        }
      } catch (err) {
        console.error('Error deleting source:', err);
        setActionError('Network error deleting target');
      }
    });
  };

  // Toggle Source Active Status
  const handleToggleSource = async (source) => {
    try {
      const res = await apiFetch(`/api/sources/${source.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !source.is_active }),
      });
      if (res.ok) {
        fetchSources();
      }
    } catch (err) {
      console.error('Error toggling source active state:', err);
    }
  };

  // Add Source Submit
  const handleAddSourceSubmit = async (e) => {
    e.preventDefault();
    setActionError('');
    try {
      const urlsArray = newSource.seed_urls.split('\n').map((u) => u.trim()).filter(Boolean);
      const res = await apiFetch('/api/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newSource.name,
          source_type: newSource.source_type,
          config: { seed_urls: urlsArray },
          poll_interval_seconds: parseInt(newSource.poll_interval_seconds),
          crawl_delay_seconds: parseFloat(newSource.crawl_delay_seconds),
          transport_type: newSource.transport_type,
        }),
      });
      if (res.ok) {
        setShowAddSourceModal(false);
        setNewSource({ name: '', source_type: 'DIRECT_SEED', seed_urls: '', poll_interval_seconds: 60, crawl_delay_seconds: 1.0, transport_type: 'direct' });
        fetchSources();
      } else {
        const errData = await res.json().catch(() => ({}));
        setActionError(errData.detail || 'Failed to create target');
      }
    } catch (err) {
      console.error('Error creating source:', err);
      setActionError('Error creating target');
    }
  };

  // Open Edit Source Modal
  const openEditModal = (src) => {
    const seedUrlsText = Array.isArray(src.config?.seed_urls) ? src.config.seed_urls.join('\n') : '';
    setEditingSource({
      id: src.id,
      name: src.name,
      source_type: src.source_type,
      seed_urls: seedUrlsText,
      poll_interval_seconds: src.poll_interval_seconds || 60,
      crawl_delay_seconds: src.crawl_delay_seconds || 1.0,
      transport_type: src.transport_type || 'direct',
      is_active: src.is_active,
    });
    setShowEditSourceModal(true);
  };

  // Submit Edit Source with Password Re-Authentication
  const handleEditSourceSubmit = (e) => {
    e.preventDefault();
    if (!editingSource) return;

    triggerReAuth(async () => {
      setActionError('');
      try {
        const urlsArray = editingSource.seed_urls.split('\n').map((u) => u.trim()).filter(Boolean);
        const res = await apiFetch(`/api/sources/${editingSource.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: editingSource.name,
            config: { seed_urls: urlsArray },
            poll_interval_seconds: parseInt(editingSource.poll_interval_seconds),
            crawl_delay_seconds: parseFloat(editingSource.crawl_delay_seconds),
            transport_type: editingSource.transport_type,
            is_active: editingSource.is_active,
          }),
        });
        if (res.ok) {
          setShowEditSourceModal(false);
          setEditingSource(null);
          fetchSources();
        } else {
          const errData = await res.json().catch(() => ({}));
          setActionError(errData.detail || 'Failed to update target');
        }
      } catch (err) {
        console.error('Error updating source:', err);
        setActionError('Error updating target');
      }
    });
  };

  // Add Global Keyword Submit
  const handleAddKeywordSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await apiFetch('/api/keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newKeyword),
      });
      if (res.ok) {
        setShowAddKeywordModal(false);
        setNewKeyword({ term: '', language: 'en', category: 'substance' });
        fetchKeywords();
      }
    } catch (err) {
      console.error('Error creating keyword:', err);
    }
  };

  const getSourceIcon = (type) => {
    switch (type) {
      case 'GOOGLE_SEARCH_DISCOVERY':
        return <Search className="w-5 h-5 text-blue-400" />;
      case 'TOR_STUB':
        return <Globe className="w-5 h-5 text-purple-400" />;
      case 'BITCOIN_CHAIN':
        return <Server className="w-5 h-5 text-yellow-400" />;
      case 'TELEGRAM_PUBLIC':
        return <MessageSquare className="w-5 h-5 text-cyan-400" />;
      case 'DIRECT_SEED':
      default:
        return <Radio className="w-5 h-5 text-emerald-400" />;
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto h-full font-mono text-slate-100">
      {/* Top Header — Heading styled identically to other view headers */}
      <div className="mb-6 flex flex-wrap justify-between items-center gap-4 border-b border-border/40 pb-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight uppercase text-foreground mb-1">
            {t('Multi-Source Data Collection & Crawler Control')}
          </h2>
          <p className="text-muted-foreground text-xs">
            {t('Monitor, configure, and control automated intelligence aggregation nodes.')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={reloadAllData}
            disabled={loading}
            className="gap-2 font-mono text-xs border-border/60 hover:bg-accent"
          >
            <RefreshCcw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            {t('Sync Pipeline')}
          </Button>
          <Button
            onClick={() => setShowAddSourceModal(true)}
            className="gap-2 font-mono text-xs font-bold"
          >
            <Plus className="w-4 h-4" />
            {t('New Crawler Target')}
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="mb-4 p-3 bg-red-950/80 border border-red-800 text-red-300 text-xs rounded-lg flex justify-between items-center">
          <span>{actionError}</span>
          <button onClick={() => setActionError('')} className="text-red-400 hover:text-red-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tabs Bar */}
      <div className="flex border-b border-border/40 mb-6 gap-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('sources')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase transition-colors border-b-2 ${
            activeTab === 'sources'
              ? 'border-emerald-500 text-emerald-400 bg-muted/40'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Radio className="w-4 h-4" />
          {t('Target Sources')} ({sources.length})
        </button>

        <button
          onClick={() => setActiveTab('keywords')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase transition-colors border-b-2 ${
            activeTab === 'keywords'
              ? 'border-emerald-500 text-emerald-400 bg-muted/40'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Tag className="w-4 h-4" />
          {t('Watchlists & Keywords')} ({keywordsData.global_keywords.length})
        </button>

        <button
          onClick={() => setActiveTab('activity')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase transition-colors border-b-2 ${
            activeTab === 'activity'
              ? 'border-emerald-500 text-emerald-400 bg-muted/40'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Activity className="w-4 h-4" />
          {t('Crawler Activity Stream')} ({activity.total})
        </button>

        <button
          onClick={() => setActiveTab('raw_records')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase transition-colors border-b-2 ${
            activeTab === 'raw_records'
              ? 'border-emerald-500 text-emerald-400 bg-muted/40'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <FileText className="w-4 h-4" />
          {t('Raw Intelligence Handoff')} ({rawRecords.total})
        </button>
      </div>

      {/* TAB 1: SOURCES & NODES */}
      {activeTab === 'sources' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sources.map((src) => (
            <div
              key={src.id}
              className="p-5 rounded-xl border bg-card hover:border-emerald-500/50 transition-all backdrop-blur"
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-muted border border-border">
                    {getSourceIcon(src.source_type)}
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-foreground">{src.name}</h4>
                    <div className="flex flex-wrap items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-emerald-400 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-800/50 font-semibold uppercase">
                        {src.source_type}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase ${
                        src.transport_type === 'tor_proxy' || src.source_type === 'TOR_STUB'
                          ? 'bg-purple-950/80 text-purple-300 border border-purple-800/50'
                          : 'bg-muted text-muted-foreground'
                      }`}>
                        {src.source_type === 'TOR_STUB' ? 'Tor Stub (Demo Mode Enforced)' : src.transport_type === 'tor_proxy' ? 'Tor Proxy' : 'Direct HTTP'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleToggleSource(src)}
                    className={`px-2.5 py-1 rounded text-xs font-bold uppercase transition-colors ${
                      src.is_active
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30'
                        : 'bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700'
                    }`}
                  >
                    {src.is_active ? 'ACTIVE' : 'DISABLED'}
                  </button>

                  <button
                    onClick={() => openEditModal(src)}
                    title="Edit Target (Requires Re-Auth)"
                    className="p-1.5 rounded hover:bg-muted text-slate-400 hover:text-emerald-400 transition-colors"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => handleDeleteSource(src.id, src.name)}
                    title="Delete Target (Requires Re-Auth)"
                    className="p-1.5 rounded hover:bg-red-950 text-slate-400 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Source parameters summary */}
              <div className="grid grid-cols-2 gap-2 text-xs bg-muted/60 p-2.5 rounded-lg border border-border/80 mb-4">
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Poll Interval:</span>
                  <span className="text-foreground font-medium">{src.poll_interval_seconds} secs</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Crawl Delay Floor:</span>
                  <span className="text-foreground font-medium">{src.crawl_delay_seconds}s</span>
                </div>
              </div>

              {/* Last Run Summary */}
              <div className="flex justify-between items-center text-xs border-t border-border pt-3">
                <div>
                  <span className="text-muted-foreground text-[11px]">Last Status: </span>
                  <span className={`font-bold ${
                    src.last_run?.status === 'COMPLETED' ? 'text-emerald-400' :
                    src.last_run?.status === 'RUNNING' ? 'text-blue-400 animate-pulse' :
                    src.last_run?.status === 'STOPPED' ? 'text-amber-400' :
                    src.last_run?.status === 'FAILED' ? 'text-red-400' : 'text-muted-foreground'
                  }`}>
                    {src.last_run?.status || 'NEVER RUN'}
                  </span>
                  {src.last_run?.records_produced !== undefined && (
                    <span className="text-muted-foreground text-[10px] ml-2">
                      ({src.last_run.records_produced} records)
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  {src.last_run?.status === 'RUNNING' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStopSource(src.id)}
                      disabled={stoppingId === src.id}
                      className="gap-1 text-xs font-mono border-amber-800/60 hover:border-amber-500 text-amber-400 bg-amber-950/40"
                    >
                      <Square className="w-3 h-3 fill-amber-400" />
                      Stop
                    </Button>
                  )}

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTriggerRun(src.id)}
                    disabled={triggeringId === src.id}
                    className="gap-1.5 text-xs font-mono border-emerald-800/60 hover:border-emerald-500 text-emerald-400 bg-emerald-950/40 hover:bg-emerald-900/40"
                  >
                    <Play className={`w-3 h-3 ${triggeringId === src.id ? 'animate-spin' : ''}`} />
                    {triggeringId === src.id ? 'Running...' : 'Run Now'}
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 2: WATCHLISTS & KEYWORDS */}
      {activeTab === 'keywords' && (
        <div className="space-y-6">
          <div className="flex flex-wrap justify-between items-center gap-4 bg-card p-4 rounded-xl border border-border">
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-emerald-400" />
              <input
                type="text"
                placeholder="Filter by Case ID (e.g. CASE-101)..."
                value={caseIdInput}
                onChange={(e) => setCaseIdInput(e.target.value)}
                className="bg-background border border-border rounded px-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500 w-64"
              />
              <Button onClick={fetchKeywords} size="sm" className="bg-emerald-800 hover:bg-emerald-700 text-xs font-mono">
                Load Case Scope
              </Button>
            </div>

            <Button
              onClick={() => setShowAddKeywordModal(true)}
              size="sm"
              className="gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Global Term
            </Button>
          </div>

          {/* Active Merged Keywords */}
          <div className="p-5 rounded-xl border border-border bg-card">
            <h3 className="text-sm font-bold text-foreground uppercase mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              Active Merged Watchlist Terms ({keywordsData.active_terms.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {keywordsData.active_terms.map((term, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 flex items-center gap-1.5"
                >
                  <Tag className="w-3 h-3 text-emerald-500" />
                  {term}
                </span>
              ))}
            </div>
          </div>

          {/* Global Keywords Catalog */}
          <div className="p-5 rounded-xl border border-border bg-card">
            <h3 className="text-sm font-bold text-foreground uppercase mb-3 flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              Global Watchlist Seed Catalog
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {keywordsData.global_keywords.map((kw) => (
                <div key={kw.id} className="p-3 rounded-lg bg-background border border-border flex justify-between items-center">
                  <div>
                    <span className="font-bold text-xs text-foreground block">{kw.term}</span>
                    <span className="text-[10px] text-muted-foreground uppercase">{kw.category || 'substance'}</span>
                  </div>
                  <span className="px-2 py-0.5 text-[10px] rounded uppercase font-bold bg-muted text-emerald-400 border border-border">
                    {kw.language}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: ACTIVITY STREAM */}
      {activeTab === 'activity' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-border bg-card flex justify-between items-center">
            <h3 className="text-sm font-bold uppercase text-foreground">Recent Crawler Runs</h3>
            <span className="text-xs text-muted-foreground">Total Runs: {activity.total}</span>
          </div>

          <div className="space-y-3">
            {activity.items.map((run) => (
              <div key={run.id} className="p-4 rounded-xl border border-border bg-card hover:bg-muted/40 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-bold text-sm text-emerald-400">{run.source_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">ID: {run.id.slice(0, 8)}...</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                    run.status === 'COMPLETED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-700' :
                    run.status === 'RUNNING' ? 'bg-blue-950 text-blue-400 border border-blue-700 animate-pulse' :
                    run.status === 'STOPPED' ? 'bg-amber-950 text-amber-400 border border-amber-700' :
                    'bg-red-950 text-red-400 border border-red-700'
                  }`}>
                    {run.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs bg-background p-3 rounded-lg border border-border my-2">
                  <div>
                    <span className="text-muted-foreground text-[10px] block uppercase">Attempted</span>
                    <span className="font-bold text-foreground">{run.urls_attempted}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px] block uppercase">Robots Skipped</span>
                    <span className="font-bold text-foreground">{run.urls_skipped_robots}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px] block uppercase">Produced</span>
                    <span className="font-bold text-emerald-400">{run.records_produced}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px] block uppercase">Relevant</span>
                    <span className="font-bold text-emerald-400">{run.records_relevant}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px] block uppercase">Errors</span>
                    <span className={`font-bold ${run.errors_count > 0 ? 'text-red-400' : 'text-foreground'}`}>{run.errors_count}</span>
                  </div>
                </div>

                {run.error_summary && (
                  <p className="text-xs text-red-400 bg-red-950/50 p-2 rounded border border-red-900/50 mt-2 font-sans">
                    <strong>Notice / Error:</strong> {run.error_summary}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: RAW RECORDS HANDOFF */}
      {activeTab === 'raw_records' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-border bg-card flex justify-between items-center">
            <h3 className="text-sm font-bold uppercase text-foreground">
              Raw Records Output Contract (<span className="text-emerald-400">pending_mapping</span>)
            </h3>
            <span className="text-xs text-muted-foreground">Items: {rawRecords.total}</span>
          </div>

          <div className="space-y-3">
            {rawRecords.items.map((rec) => (
              <div key={rec.id} className="p-4 rounded-xl border border-border bg-card hover:border-emerald-800 transition-all">
                <div className="flex justify-between items-start mb-2">
                  <div className="max-w-xl">
                    <span className="text-xs font-bold text-emerald-400 truncate block">{rec.url}</span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded uppercase font-semibold">
                        Lang: {rec.language || 'en'}
                      </span>
                      <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-1.5 py-0.5 rounded font-mono truncate max-w-[200px]">
                        HASH: {rec.content_hash}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2.5 py-1 rounded-full font-bold uppercase bg-emerald-950 text-emerald-300 border border-emerald-700">
                      {rec.relevance_label} ({Math.round((rec.relevance_confidence || 0) * 100)}%)
                    </span>
                    <Button size="sm" variant="outline" onClick={() => setSelectedRecord(rec)} className="gap-1 text-xs font-mono">
                      <Eye className="w-3.5 h-3.5" /> Inspect
                    </Button>
                  </div>
                </div>

                <p className="text-xs text-slate-300 line-clamp-2 bg-background p-2.5 rounded border border-border font-sans">
                  {rec.cleaned_text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* INSPECT RECORD MODAL */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/50 rounded-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6 font-mono shadow-2xl relative animate-in fade-in zoom-in-95">
            <button onClick={() => setSelectedRecord(null)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-100">
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold uppercase text-emerald-400 mb-1 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              Raw Record Evidence Detail
            </h3>
            <p className="text-xs text-slate-400 mb-4">{selectedRecord.url}</p>

            <div className="space-y-4 text-xs">
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Content Hash (SHA-256):</span>
                  <span className="text-emerald-400 font-mono break-all">{selectedRecord.content_hash}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">AI Reasoning:</span>
                  <span className="text-slate-300">{selectedRecord.relevance_reasoning || 'N/A'}</span>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-slate-300 uppercase mb-1">Extracted Candidate Entities</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedRecord.extracted_candidates?.map((cand, i) => (
                    <span key={i} className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-semibold text-emerald-300 flex items-center gap-1">
                      <Hash className="w-3 h-3 text-emerald-500" />
                      [{cand.type}] {cand.value}
                    </span>
                  )) || <span className="text-slate-500">None extracted</span>}
                </div>
              </div>

              <div>
                <h4 className="font-bold text-slate-300 uppercase mb-1">Cleaned Body Text</h4>
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 max-h-60 overflow-y-auto font-sans text-slate-200 whitespace-pre-wrap leading-relaxed">
                  {selectedRecord.cleaned_text}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ADD SOURCE MODAL */}
      {showAddSourceModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/50 rounded-xl max-w-lg w-full p-6 font-mono shadow-2xl relative">
            <button onClick={() => setShowAddSourceModal(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-100">
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold uppercase text-emerald-400 mb-4">Add New Crawler Target</h3>
            <form onSubmit={handleAddSourceSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Source Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Surface Forum Monitor"
                  value={newSource.name}
                  onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Source Type</label>
                <select
                  value={newSource.source_type}
                  onChange={(e) => setNewSource({ ...newSource, source_type: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                >
                  <option value="DIRECT_SEED">DIRECT_SEED (Public Web)</option>
                  <option value="GOOGLE_SEARCH_DISCOVERY">GOOGLE_SEARCH_DISCOVERY (Tavily API)</option>
                  <option value="BITCOIN_CHAIN">BITCOIN_CHAIN (Public Ledger)</option>
                  <option value="TELEGRAM_PUBLIC">TELEGRAM_PUBLIC (Public Channels)</option>
                  <option value="TOR_STUB">TOR_STUB (Architecture Stub)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Seed URLs / Channels (one per line)</label>
                <textarea
                  rows={3}
                  placeholder="https://en.wikipedia.org/wiki/Heroin"
                  value={newSource.seed_urls}
                  onChange={(e) => setNewSource({ ...newSource, seed_urls: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Poll Interval (seconds)</label>
                  <input
                    type="number"
                    min="5"
                    value={newSource.poll_interval_seconds}
                    onChange={(e) => setNewSource({ ...newSource, poll_interval_seconds: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Crawl Delay (s)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    value={newSource.crawl_delay_seconds}
                    onChange={(e) => setNewSource({ ...newSource, crawl_delay_seconds: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setShowAddSourceModal(false)} className="text-xs font-mono">
                  Cancel
                </Button>
                <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs font-mono">
                  Create Target
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT SOURCE MODAL */}
      {showEditSourceModal && editingSource && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/50 rounded-xl max-w-lg w-full p-6 font-mono shadow-2xl relative">
            <button onClick={() => setShowEditSourceModal(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-100">
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold uppercase text-emerald-400 mb-1">Edit Crawler Target</h3>
            <p className="text-[11px] text-amber-400 mb-4 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> Sensitive Operation: Password Re-Authentication will be required on submit.
            </p>

            <form onSubmit={handleEditSourceSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Source Name</label>
                <input
                  type="text"
                  required
                  value={editingSource.name}
                  onChange={(e) => setEditingSource({ ...editingSource, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Seed URLs / Channels (one per line)</label>
                <textarea
                  rows={3}
                  value={editingSource.seed_urls}
                  onChange={(e) => setEditingSource({ ...editingSource, seed_urls: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Poll Interval (seconds)</label>
                  <input
                    type="number"
                    min="5"
                    value={editingSource.poll_interval_seconds}
                    onChange={(e) => setEditingSource({ ...editingSource, poll_interval_seconds: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Crawl Delay (s)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    value={editingSource.crawl_delay_seconds}
                    onChange={(e) => setEditingSource({ ...editingSource, crawl_delay_seconds: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="editIsActive"
                  checked={editingSource.is_active}
                  onChange={(e) => setEditingSource({ ...editingSource, is_active: e.target.checked })}
                  className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0"
                />
                <label htmlFor="editIsActive" className="text-slate-300 text-xs select-none">
                  Enable Source (Active)
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setShowEditSourceModal(false)} className="text-xs font-mono">
                  Cancel
                </Button>
                <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs font-mono">
                  Authorize & Save
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD KEYWORD MODAL */}
      {showAddKeywordModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/50 rounded-xl max-w-md w-full p-6 font-mono shadow-2xl relative">
            <button onClick={() => setShowAddKeywordModal(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-100">
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold uppercase text-emerald-400 mb-4">Add Global Watchlist Term</h3>
            <form onSubmit={handleAddKeywordSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Term</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. fentanyl"
                  value={newKeyword.term}
                  onChange={(e) => setNewKeyword({ ...newKeyword, term: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Language</label>
                  <select
                    value={newKeyword.language}
                    onChange={(e) => setNewKeyword({ ...newKeyword, language: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="en">English (en)</option>
                    <option value="hi">Hindi (hi)</option>
                    <option value="pa">Punjabi (pa)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 mb-1">Category</label>
                  <select
                    value={newKeyword.category}
                    onChange={(e) => setNewKeyword({ ...newKeyword, category: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="substance">Substance</option>
                    <option value="slang">Slang</option>
                    <option value="marketplace_term">Marketplace Term</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setShowAddKeywordModal(false)} className="text-xs font-mono">
                  Cancel
                </Button>
                <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs font-mono">
                  Add Term
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
