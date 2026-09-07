import { useEffect, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
  Key,
  Fingerprint,
  Layers,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Activity,
  Cpu,
  Hash,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { Button } from '../ui/button';
import { fetchAlerts, fetchSuspiciousActivities } from '../../api/alertsApi';

// Mapping backend activity types to human-readable names
const ACTIVITY_TYPE_LABELS = {
  high_relevance: 'High Relevance',
  keyword_burst: 'Keyword Burst',
  entity_indicator: 'Entity Indicator',
  combined_signal: 'Combined Signal',
};

// Activity type icons
function getActivityIcon(type) {
  switch (type) {
    case 'high_relevance':
      return <ShieldAlert className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />;
    case 'keyword_burst':
      return <Key className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" />;
    case 'entity_indicator':
      return <Fingerprint className="w-5 h-5 text-cyan-400 mt-0.5 flex-shrink-0" />;
    case 'combined_signal':
      return <Layers className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />;
    default:
      return <TrendingUp className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />;
  }
}

// Severity visual styling helpers
function getSeverityBadge(severity) {
  const s = (severity || '').toLowerCase();
  if (s === 'red') {
    return {
      label: 'CRITICAL',
      badgeClass: 'bg-red-500/20 text-red-400 border border-red-500/40',
      cardClass: 'bg-red-500/5 border-red-500/30 text-foreground hover:border-red-500/50',
      iconClass: 'text-red-500',
    };
  }
  if (s === 'yellow') {
    return {
      label: 'WARNING',
      badgeClass: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40',
      cardClass: 'bg-yellow-500/5 border-yellow-500/30 text-foreground hover:border-yellow-500/50',
      iconClass: 'text-yellow-500',
    };
  }
  return {
    label: 'INFO',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
    cardClass: 'bg-emerald-500/5 border-emerald-500/30 text-foreground hover:border-emerald-500/50',
    iconClass: 'text-emerald-500',
  };
}

// Status visual badge styling
function getStatusBadge(status) {
  const st = (status || '').toLowerCase();
  if (st === 'active' || st === 'open') {
    return 'bg-amber-500/15 text-amber-400 border border-amber-500/30';
  }
  if (st === 'acknowledged') {
    return 'bg-blue-500/15 text-blue-400 border border-blue-500/30';
  }
  if (st === 'resolved') {
    return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
  }
  if (st === 'dismissed') {
    return 'bg-zinc-500/15 text-zinc-400 border border-zinc-500/30';
  }
  return 'bg-muted text-muted-foreground border border-border/40';
}

// Small helper component to copy identifiers with feedback
function CopyableId({ label, value }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e) => {
    e.stopPropagation();
    if (!value) return;
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  if (!value) return null;

  return (
    <div
      onClick={handleCopy}
      title={`Click to copy: ${value}`}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono bg-muted/60 border border-border/50 rounded hover:bg-primary/10 hover:border-primary/40 cursor-pointer transition-colors text-muted-foreground hover:text-foreground"
    >
      <span className="opacity-70">{label}:</span>
      <span className="font-semibold text-foreground truncate max-w-[140px]">{value}</span>
      {copied ? (
        <Check className="w-3 h-3 text-emerald-400 flex-shrink-0" />
      ) : (
        <Copy className="w-3 h-3 opacity-60 flex-shrink-0" />
      )}
    </div>
  );
}

export default function AlertsFeed() {
  const { t } = useTranslation();

  // Active view tab (all, alerts, suspicious)
  const [activeTab, setActiveTab] = useState('all');

  // Data state
  const [alerts, setAlerts] = useState([]);
  const [suspicious, setSuspicious] = useState([]);

  // Summary counts state (cached from full or unfiltered load)
  const [summaryCounts, setSummaryCounts] = useState({
    critical: 0,
    warning: 0,
    info: 0,
    openSuspicious: 0,
  });

  // Loading and error states
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [loadingSuspicious, setLoadingSuspicious] = useState(true);
  const [alertsError, setAlertsError] = useState(null);
  const [suspiciousError, setSuspiciousError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Alert Filters
  const [alertSeverityFilter, setAlertSeverityFilter] = useState('all');
  const [alertStatusFilter, setAlertStatusFilter] = useState('all');
  const [alertSearchTerm, setAlertSearchTerm] = useState('');

  // Suspicious Activity Filters
  const [suspiciousStatusFilter, setSuspiciousStatusFilter] = useState('all');
  const [suspiciousSearchTerm, setSuspiciousSearchTerm] = useState('');

  // Expanded evidence state map (id -> boolean)
  const [expandedEvidence, setExpandedEvidence] = useState({});

  const toggleEvidence = (id) => {
    setExpandedEvidence((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  // Fetch alerts from backend
  const loadAlerts = useCallback(async (severity = alertSeverityFilter, status = alertStatusFilter) => {
    setLoadingAlerts(true);
    setAlertsError(null);
    try {
      const data = await fetchAlerts({ severity, status, limit: 100 });
      const items = Array.isArray(data) ? data : [];
      setAlerts(items);

      // If fetching unfiltered, update the summary counts
      if (severity === 'all' && status === 'all') {
        const crit = items.filter((a) => (a.severity || '').toLowerCase() === 'red').length;
        const warn = items.filter((a) => (a.severity || '').toLowerCase() === 'yellow').length;
        const info = items.filter((a) => (a.severity || '').toLowerCase() === 'green').length;
        setSummaryCounts((prev) => ({ ...prev, critical: crit, warning: warn, info }));
      }
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setAlertsError(err.message || 'Failed to load alerts feed');
    } finally {
      setLoadingAlerts(false);
    }
  }, [alertSeverityFilter, alertStatusFilter]);

  // Fetch suspicious activities from backend
  const loadSuspicious = useCallback(async (status = suspiciousStatusFilter) => {
    setLoadingSuspicious(true);
    setSuspiciousError(null);
    try {
      const data = await fetchSuspiciousActivities({ status, limit: 100 });
      const items = Array.isArray(data) ? data : [];
      setSuspicious(items);

      // If fetching unfiltered, update open suspicious count
      if (status === 'all') {
        const openCount = items.filter((s) => (s.status || '').toLowerCase() === 'open').length;
        setSummaryCounts((prev) => ({ ...prev, openSuspicious: openCount }));
      }
    } catch (err) {
      console.error('Error fetching suspicious activities:', err);
      setSuspiciousError(err.message || 'Failed to load suspicious activities');
    } finally {
      setLoadingSuspicious(false);
    }
  }, [suspiciousStatusFilter]);

  // Initial load of both feeds
  useEffect(() => {
    loadAlerts(alertSeverityFilter, alertStatusFilter);
  }, [alertSeverityFilter, alertStatusFilter, loadAlerts]);

  useEffect(() => {
    loadSuspicious(suspiciousStatusFilter);
  }, [suspiciousStatusFilter, loadSuspicious]);

  // Refresh both feeds manually
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([
      loadAlerts(alertSeverityFilter, alertStatusFilter),
      loadSuspicious(suspiciousStatusFilter),
    ]);
    setIsRefreshing(false);
  };

  // Client-side search filtering on currently loaded alert items
  const filteredAlerts = useMemo(() => {
    if (!alertSearchTerm.trim()) return alerts;
    const q = alertSearchTerm.toLowerCase();
    return alerts.filter((a) => {
      const msg = (a.message || '').toLowerCase();
      const caseId = (a.case_id || '').toLowerCase();
      const rawId = (a.raw_record_id || '').toLowerCase();
      const sev = (a.severity || '').toLowerCase();
      const stat = (a.status || '').toLowerCase();
      return (
        msg.includes(q) ||
        caseId.includes(q) ||
        rawId.includes(q) ||
        sev.includes(q) ||
        stat.includes(q)
      );
    });
  }, [alerts, alertSearchTerm]);

  // Client-side search filtering on currently loaded suspicious items
  const filteredSuspicious = useMemo(() => {
    if (!suspiciousSearchTerm.trim()) return suspicious;
    const q = suspiciousSearchTerm.toLowerCase();
    return suspicious.filter((act) => {
      const desc = (act.description || '').toLowerCase();
      const type = (act.type || '').toLowerCase();
      const typeLabel = (ACTIVITY_TYPE_LABELS[act.type] || '').toLowerCase();
      const caseId = (act.case_id || '').toLowerCase();
      const rawId = (act.raw_record_id || '').toLowerCase();
      const stat = (act.status || '').toLowerCase();
      return (
        desc.includes(q) ||
        type.includes(q) ||
        typeLabel.includes(q) ||
        caseId.includes(q) ||
        rawId.includes(q) ||
        stat.includes(q)
      );
    });
  }, [suspicious, suspiciousSearchTerm]);

  // Derived counts for top summary (fallback to current loaded count if summary is 0)
  const displaySummary = useMemo(() => {
    const critical = summaryCounts.critical || alerts.filter((a) => (a.severity || '').toLowerCase() === 'red').length;
    const warning = summaryCounts.warning || alerts.filter((a) => (a.severity || '').toLowerCase() === 'yellow').length;
    const info = summaryCounts.info || alerts.filter((a) => (a.severity || '').toLowerCase() === 'green').length;
    const openSuspicious = summaryCounts.openSuspicious || suspicious.filter((s) => (s.status || '').toLowerCase() === 'open').length;
    return { critical, warning, info, openSuspicious };
  }, [summaryCounts, alerts, suspicious]);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-5xl mx-auto space-y-8 font-sans">
      {/* View Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/50 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="w-6 h-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight uppercase font-mono text-foreground">
              {t('Alerts & Suspicious Activity Feed')}
            </h1>
          </div>
          <p className="text-muted-foreground text-xs font-mono mt-1">
            {t('Real-time automated alert generation and explainable AI pattern detection.')}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Navigation Tab Pills */}
          <div className="flex bg-muted/60 p-1 rounded-lg border border-border/50 text-xs font-mono">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                activeTab === 'all'
                  ? 'bg-primary text-primary-foreground font-bold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('All Feeds')}
            </button>
            <button
              onClick={() => setActiveTab('alerts')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                activeTab === 'alerts'
                  ? 'bg-primary text-primary-foreground font-bold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('Alerts')} ({alerts.length})
            </button>
            <button
              onClick={() => setActiveTab('suspicious')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                activeTab === 'suspicious'
                  ? 'bg-primary text-primary-foreground font-bold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('Suspicious')} ({suspicious.length})
            </button>
          </div>

          {/* Refresh Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing || loadingAlerts || loadingSuspicious}
            className="font-mono text-xs gap-2 border-border/60 hover:border-primary/50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-primary' : ''}`} />
            <span>{isRefreshing ? t('Refreshing...') : t('Refresh Feed')}</span>
          </Button>
        </div>
      </div>

      {/* Top Tactical Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Critical Alerts */}
        <div className="p-4 bracket-border bg-card/40 border border-border/40 flex flex-col gap-1 rounded-lg">
          <span className="text-[11px] font-mono tracking-wider uppercase text-red-400 flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            {t('Critical (Red)')}
          </span>
          <span className="text-3xl font-black font-mono text-red-500 mt-1">
            {displaySummary.critical}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {t('Immediate action required')}
          </span>
        </div>

        {/* Warning Alerts */}
        <div className="p-4 bracket-border bg-card/40 border border-border/40 flex flex-col gap-1 rounded-lg">
          <span className="text-[11px] font-mono tracking-wider uppercase text-yellow-400 flex items-center gap-1.5 font-semibold">
            <AlertCircle className="w-3.5 h-3.5 text-yellow-400" />
            {t('Warning (Yellow)')}
          </span>
          <span className="text-3xl font-black font-mono text-yellow-400 mt-1">
            {displaySummary.warning}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {t('Moderate threat threshold')}
          </span>
        </div>

        {/* Info Alerts */}
        <div className="p-4 bracket-border bg-card/40 border border-border/40 flex flex-col gap-1 rounded-lg">
          <span className="text-[11px] font-mono tracking-wider uppercase text-emerald-400 flex items-center gap-1.5 font-semibold">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            {t('Info (Green)')}
          </span>
          <span className="text-3xl font-black font-mono text-emerald-400 mt-1">
            {displaySummary.info}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {t('Informational indicators')}
          </span>
        </div>

        {/* Open Suspicious Activities */}
        <div className="p-4 bracket-border bg-card/40 border border-border/40 flex flex-col gap-1 rounded-lg">
          <span className="text-[11px] font-mono tracking-wider uppercase text-primary flex items-center gap-1.5 font-semibold">
            <Activity className="w-3.5 h-3.5 text-primary" />
            {t('Open Detections')}
          </span>
          <span className="text-3xl font-black font-mono text-primary mt-1">
            {displaySummary.openSuspicious}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {t('Unresolved suspicious patterns')}
          </span>
        </div>
      </div>

      {/* SECTION 1: AUTOMATED ALERTS */}
      {(activeTab === 'all' || activeTab === 'alerts') && (
        <div className="space-y-4 pt-2">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold tracking-tight uppercase font-mono flex items-center gap-2 text-foreground">
                <AlertTriangle className="w-5 h-5 text-primary" />
                {t('Automated Alerts')}
              </h2>
              <p className="text-muted-foreground text-xs font-mono">
                {t('Deterministic risk triggers computed from ingested crawler intelligence.')}
              </p>
            </div>

            {/* Alert Filter Bar */}
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              {/* Search Bar */}
              <div className="relative min-w-[200px]">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={t('Search message, case, ID...')}
                  value={alertSearchTerm}
                  onChange={(e) => setAlertSearchTerm(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 bg-background border border-border/60 rounded-md text-xs focus:outline-none focus:border-primary text-foreground"
                />
              </div>

              {/* Severity Filter */}
              <div className="flex items-center gap-1 bg-card border border-border/60 rounded-md p-0.5">
                <span className="px-2 py-1 text-[10px] text-muted-foreground uppercase font-bold">{t('Sev')}:</span>
                {['all', 'red', 'yellow', 'green'].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setAlertSeverityFilter(sev)}
                    className={`px-2 py-1 rounded text-[11px] capitalize transition-colors ${
                      alertSeverityFilter === sev
                        ? 'bg-primary text-primary-foreground font-bold'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {t(sev)}
                  </button>
                ))}
              </div>

              {/* Status Filter */}
              <div className="flex items-center gap-1 bg-card border border-border/60 rounded-md p-0.5">
                <span className="px-2 py-1 text-[10px] text-muted-foreground uppercase font-bold">{t('Status')}:</span>
                {['all', 'active', 'acknowledged', 'resolved'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setAlertStatusFilter(st)}
                    className={`px-2 py-1 rounded text-[11px] capitalize transition-colors ${
                      alertStatusFilter === st
                        ? 'bg-primary text-primary-foreground font-bold'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {t(st)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Alert List Container */}
          {loadingAlerts ? (
            <div className="space-y-3 font-mono">
              {[1, 2, 3].map((n) => (
                <div key={n} className="p-4 rounded-xl border border-border/40 bg-card/30 animate-pulse flex items-start gap-4">
                  <div className="w-5 h-5 bg-muted rounded-full mt-0.5 flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-muted rounded w-3/4" />
                    <div className="h-3 bg-muted rounded w-1/4" />
                  </div>
                </div>
              ))}
            </div>
          ) : alertsError ? (
            <div className="p-6 border border-destructive/40 bg-destructive/10 rounded-xl font-mono text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-destructive mx-auto" />
              <p className="text-sm text-destructive font-semibold">{alertsError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadAlerts(alertSeverityFilter, alertStatusFilter)}
                className="text-xs font-mono border-destructive/40 hover:bg-destructive/10"
              >
                {t('Retry Loading Alerts')}
              </Button>
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="p-8 border border-border/40 rounded-xl bg-card/20 text-center font-mono space-y-2">
              <ShieldCheck className="w-8 h-8 text-muted-foreground/60 mx-auto" />
              <p className="text-sm font-semibold text-foreground">
                {alerts.length === 0
                  ? t('No active alerts recorded')
                  : t('No alerts match the selected filters')}
              </p>
              <p className="text-xs text-muted-foreground">
                {alerts.length === 0
                  ? t('System detection rules are actively monitoring incoming intelligence records.')
                  : t('Try relaxing your severity or status filter criteria.')}
              </p>
              {alerts.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setAlertSeverityFilter('all');
                    setAlertStatusFilter('all');
                    setAlertSearchTerm('');
                  }}
                  className="text-xs text-primary hover:text-primary/80"
                >
                  {t('Clear Filters')}
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-3 font-mono">
              {filteredAlerts.map((alert) => {
                const sevInfo = getSeverityBadge(alert.severity);
                return (
                  <div
                    key={alert.id}
                    className={`p-4 rounded-xl border transition-all duration-200 flex flex-col md:flex-row md:items-start justify-between gap-4 ${sevInfo.cardClass}`}
                  >
                    <div className="flex items-start gap-3.5 flex-1">
                      <AlertTriangle className={`w-5 h-5 flex-shrink-0 mt-0.5 ${sevInfo.iconClass}`} />
                      <div className="space-y-2 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded tracking-wider ${sevInfo.badgeClass}`}>
                            {sevInfo.label}
                          </span>
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded uppercase ${getStatusBadge(alert.status)}`}>
                            {alert.status || 'ACTIVE'}
                          </span>
                          <span className="text-[11px] text-muted-foreground opacity-80 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : 'N/A'}
                          </span>
                        </div>

                        <p className="font-semibold text-sm leading-snug text-foreground">
                          {t(alert.message) || alert.message}
                        </p>

                        {/* Case & Record Identifiers */}
                        {(alert.case_id || alert.raw_record_id || alert.suspicious_activity_id) && (
                          <div className="flex flex-wrap items-center gap-2 pt-1">
                            {alert.case_id && <CopyableId label="CASE" value={alert.case_id} />}
                            {alert.raw_record_id && <CopyableId label="RAW RECORD" value={alert.raw_record_id} />}
                            {alert.suspicious_activity_id && (
                              <CopyableId label="ACTIVITY REF" value={alert.suspicious_activity_id} />
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* SECTION 2: SUSPICIOUS ACTIVITY DETECTION */}
      {(activeTab === 'all' || activeTab === 'suspicious') && (
        <div className="space-y-4 pt-4 border-t border-border/40">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold tracking-tight uppercase font-mono flex items-center gap-2 text-foreground">
                <Layers className="w-5 h-5 text-primary" />
                {t('Suspicious Activity Detection')}
              </h2>
              <p className="text-muted-foreground text-xs font-mono">
                {t('Explainable rule-based pattern analysis across raw crawler intelligence.')}
              </p>
            </div>

            {/* Suspicious Activity Filter Bar */}
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              {/* Search Bar */}
              <div className="relative min-w-[200px]">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={t('Search pattern, rule, case...')}
                  value={suspiciousSearchTerm}
                  onChange={(e) => setSuspiciousSearchTerm(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 bg-background border border-border/60 rounded-md text-xs focus:outline-none focus:border-primary text-foreground"
                />
              </div>

              {/* Status Filter */}
              <div className="flex items-center gap-1 bg-card border border-border/60 rounded-md p-0.5">
                <span className="px-2 py-1 text-[10px] text-muted-foreground uppercase font-bold">{t('Status')}:</span>
                {['all', 'open', 'acknowledged', 'resolved', 'dismissed'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setSuspiciousStatusFilter(st)}
                    className={`px-2 py-1 rounded text-[11px] capitalize transition-colors ${
                      suspiciousStatusFilter === st
                        ? 'bg-primary text-primary-foreground font-bold'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {t(st)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Suspicious Activity List Container */}
          {loadingSuspicious ? (
            <div className="space-y-3 font-mono">
              {[1, 2, 3].map((n) => (
                <div key={n} className="p-4 rounded-xl border border-border/40 bg-card/30 animate-pulse flex items-start gap-4">
                  <div className="w-5 h-5 bg-muted rounded-full mt-0.5 flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-muted rounded w-3/4" />
                    <div className="h-3 bg-muted rounded w-1/4" />
                  </div>
                </div>
              ))}
            </div>
          ) : suspiciousError ? (
            <div className="p-6 border border-destructive/40 bg-destructive/10 rounded-xl font-mono text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-destructive mx-auto" />
              <p className="text-sm text-destructive font-semibold">{suspiciousError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadSuspicious(suspiciousStatusFilter)}
                className="text-xs font-mono border-destructive/40 hover:bg-destructive/10"
              >
                {t('Retry Loading Suspicious Activities')}
              </Button>
            </div>
          ) : filteredSuspicious.length === 0 ? (
            <div className="p-8 border border-border/40 rounded-xl bg-card/20 text-center font-mono space-y-2">
              <CheckCircle2 className="w-8 h-8 text-muted-foreground/60 mx-auto" />
              <p className="text-sm font-semibold text-foreground">
                {suspicious.length === 0
                  ? t('No suspicious activities recorded')
                  : t('No suspicious activities match the selected filters')}
              </p>
              <p className="text-xs text-muted-foreground">
                {suspicious.length === 0
                  ? t('Detection pipeline has not flagged high-risk patterns in current records.')
                  : t('Try relaxing your status filter criteria.')}
              </p>
              {suspicious.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSuspiciousStatusFilter('all');
                    setSuspiciousSearchTerm('');
                  }}
                  className="text-xs text-primary hover:text-primary/80"
                >
                  {t('Clear Filters')}
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-4 font-mono">
              {filteredSuspicious.map((act) => {
                const isExpanded = !!expandedEvidence[act.id];
                const confidencePct = act.confidence !== null && act.confidence !== undefined
                  ? (act.confidence * 100).toFixed(0)
                  : 'N/A';
                const typeFriendly = ACTIVITY_TYPE_LABELS[act.type] || (act.type || 'Detection').replace(/_/g, ' ');

                return (
                  <div
                    key={act.id}
                    className="p-5 rounded-xl border border-border/50 bg-card/60 backdrop-blur-sm text-card-foreground shadow-sm hover:border-primary/40 transition-colors"
                  >
                    <div className="flex items-start gap-4">
                      {getActivityIcon(act.type)}

                      <div className="flex-1 space-y-2">
                        {/* Header & Badges */}
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-bold font-mono tracking-wider bg-primary/15 text-primary border border-primary/30 px-2.5 py-0.5 rounded uppercase">
                              {typeFriendly}
                            </span>
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded uppercase ${getStatusBadge(act.status)}`}>
                              {act.status || 'OPEN'}
                            </span>
                            {act.date && (
                              <span className="text-[11px] text-muted-foreground opacity-80 flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {act.date}
                              </span>
                            )}
                          </div>

                          {/* Confidence Score Pill */}
                          <div className="flex items-center gap-2">
                            <div className="text-right">
                              <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">
                                {t('Confidence')}
                              </span>
                              <span className="text-sm font-bold text-foreground">
                                {confidencePct}%
                              </span>
                            </div>
                            <div className="w-12 h-2 bg-muted rounded-full overflow-hidden border border-border/50">
                              <div
                                className="h-full bg-primary"
                                style={{ width: `${Math.min(Number(confidencePct) || 0, 100)}%` }}
                              />
                            </div>
                          </div>
                        </div>

                        {/* Description */}
                        <p className="font-semibold text-sm leading-relaxed text-foreground">
                          {t(act.description) || act.description}
                        </p>

                        {/* Associated IDs */}
                        {(act.case_id || act.raw_record_id) && (
                          <div className="flex flex-wrap items-center gap-2 pt-1">
                            {act.case_id && <CopyableId label="CASE" value={act.case_id} />}
                            {act.raw_record_id && <CopyableId label="RAW RECORD" value={act.raw_record_id} />}
                          </div>
                        )}

                        {/* Explainable Evidence Accordion Toggle */}
                        <div className="pt-2">
                          <button
                            onClick={() => toggleEvidence(act.id)}
                            className="inline-flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 font-mono transition-colors focus:outline-none"
                          >
                            <span>{isExpanded ? t('Hide Explainable Evidence') : t('Inspect Explainable Evidence')}</span>
                            {isExpanded ? (
                              <ChevronUp className="w-3.5 h-3.5" />
                            ) : (
                              <ChevronDown className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>

                        {/* Expanded Evidence Breakdown */}
                        {isExpanded && (
                          <div className="mt-3 p-4 rounded-lg bg-background/70 border border-border/60 space-y-3.5 animate-in fade-in duration-300">
                            <div className="flex items-center justify-between border-b border-border/40 pb-2">
                              <div className="flex items-center gap-2">
                                <Cpu className="w-4 h-4 text-primary" />
                                <span className="text-xs font-bold uppercase tracking-wider text-foreground">
                                  {t('Detection Signal Breakdown')}
                                </span>
                              </div>
                              {act.evidence_summary?.score !== undefined && (
                                <span className="text-xs font-mono bg-muted/80 px-2 py-0.5 rounded border border-border/40 text-foreground">
                                  {t('Overall Score')}: {(act.evidence_summary.score * 100).toFixed(0)}%
                                </span>
                              )}
                            </div>

                            {/* Aggregated Reasons */}
                            {Array.isArray(act.evidence_summary?.reasons) && act.evidence_summary.reasons.length > 0 && (
                              <div className="space-y-1.5">
                                <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                                  {t('Trigger Reasons')}:
                                </span>
                                <div className="flex flex-wrap gap-1.5">
                                  {act.evidence_summary.reasons.map((reason, idx) => (
                                    <span
                                      key={idx}
                                      className="px-2 py-0.5 text-[11px] font-mono bg-card border border-border/50 rounded text-foreground/90 break-all"
                                    >
                                      {reason}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Individual Detection Signals */}
                            {Array.isArray(act.evidence_summary?.signals) && act.evidence_summary.signals.length > 0 && (
                              <div className="space-y-2 pt-1">
                                <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                                  {t('Rule Confidence & Explanations')}:
                                </span>
                                <div className="grid gap-2">
                                  {act.evidence_summary.signals.map((sig, sIdx) => {
                                    const sigRule = ACTIVITY_TYPE_LABELS[sig.rule] || (sig.rule || 'Rule').replace(/_/g, ' ');
                                    const sigConf = sig.confidence !== undefined && sig.confidence !== null
                                      ? (sig.confidence * 100).toFixed(0)
                                      : 'N/A';
                                    return (
                                      <div
                                        key={sIdx}
                                        className="p-2.5 rounded bg-card/40 border border-border/40 text-xs space-y-1.5"
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className="font-bold text-primary flex items-center gap-1.5">
                                            <Hash className="w-3 h-3 text-muted-foreground" />
                                            {sigRule}
                                          </span>
                                          <span className="text-[11px] font-mono text-muted-foreground">
                                            {t('Confidence')}: {sigConf}%
                                          </span>
                                        </div>
                                        {Array.isArray(sig.reasons) && sig.reasons.length > 0 && (
                                          <ul className="list-disc list-inside space-y-0.5 text-[11px] text-muted-foreground pl-1">
                                            {sig.reasons.map((r, rIdx) => (
                                              <li key={rIdx} className="break-all">
                                                {r}
                                              </li>
                                            ))}
                                          </ul>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {/* Fallback if evidence_summary is empty */}
                            {(!act.evidence_summary ||
                              (!act.evidence_summary.reasons?.length && !act.evidence_summary.signals?.length)) && (
                              <p className="text-xs text-muted-foreground italic">
                                {t('No detailed signal breakdown recorded for this detection.')}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
