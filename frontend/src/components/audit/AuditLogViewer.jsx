import React, { useState, useEffect } from 'react';
import { KeyRound, Download, RefreshCw, Filter, ShieldCheck, AlertTriangle } from 'lucide-react';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';

export default function AuditLogViewer() {
  const { triggerReAuth } = useAuth();
  const [logs, setLogs] = useState([]);
  const [actionFilter, setActionFilter] = useState('');
  const [resultFilter, setResultFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchLogs = () => {
    setError('');

    // Viewing audit logs requires recent reauth (PRD Section 9)
    triggerReAuth(async () => {
      setLoading(true);
      try {
        const queryParams = new URLSearchParams();
        if (actionFilter) queryParams.append('action', actionFilter);
        if (resultFilter) queryParams.append('result', resultFilter);

        const res = await fetch(`/api/audit-logs?${queryParams.toString()}`);
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || 'Failed to fetch audit logs');
        }
        const data = await res.json();
        setLogs(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    });
  };

  const handleExport = () => {
    setError('');

    triggerReAuth(async () => {
      try {
        const res = await fetch('/api/audit-logs/export');
        if (!res.ok) throw new Error('Failed to export audit logs');
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `darknight_audit_trail_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } catch (err) {
        setError(err.message);
      }
    });
  };

  return (
    <div className="space-y-5 font-mono">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-foreground flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-amber-400" /> Immutable Audit Log Trail
          </h3>
          <p className="text-xs text-muted-foreground">
            Append-only security and activity record (UPDATE & DELETE strictly disabled).
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchLogs} disabled={loading} className="text-xs gap-1">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Load Audit Trail
          </Button>
          <Button size="sm" onClick={handleExport} className="text-xs gap-1 bg-amber-600 hover:bg-amber-700 text-white">
            <Download className="w-3.5 h-3.5" /> Export CSV
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex gap-3 bg-card p-3 rounded-lg border border-border/60">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Filter className="w-4 h-4 text-primary" /> Filter:
        </div>
        <input
          type="text"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          placeholder="Action (e.g. LOGIN_SUCCESS, ACCESS_GRANTED)"
          className="bg-background border border-border/60 rounded px-3 py-1 text-xs focus:border-primary flex-1"
        />
        <select
          value={resultFilter}
          onChange={(e) => setResultFilter(e.target.value)}
          className="bg-background border border-border/60 rounded px-3 py-1 text-xs focus:border-primary"
        >
          <option value="">All Results</option>
          <option value="SUCCESS">SUCCESS</option>
          <option value="FAILURE">FAILURE</option>
          <option value="DENIED">DENIED</option>
        </select>
        <Button size="sm" onClick={fetchLogs} className="text-xs">
          Apply Filter
        </Button>
      </div>

      <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/40 border-b border-border/60 text-muted-foreground uppercase text-[11px]">
            <tr>
              <th className="p-3">Timestamp (UTC)</th>
              <th className="p-3">Officer ID & Role</th>
              <th className="p-3">Security Action</th>
              <th className="p-3">Resource Target</th>
              <th className="p-3">Result</th>
              <th className="p-3">IP Address</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 font-mono text-[11px]">
            {logs.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-6 text-center text-muted-foreground">
                  No audit log entries loaded. Click "Load Audit Trail" (re-authentication required).
                </td>
              </tr>
            ) : (
              logs.map((l) => (
                <tr key={l.id} className="hover:bg-muted/20">
                  <td className="p-3 text-muted-foreground">
                    {l.timestamp ? new Date(l.timestamp).toLocaleString() : 'N/A'}
                  </td>
                  <td className="p-3">
                    <span className="font-bold text-foreground">User #{l.user_id || 'System'}</span>
                    <span className="text-muted-foreground block text-[10px]">{l.role || 'Unauthenticated'}</span>
                  </td>
                  <td className="p-3 font-semibold text-primary">{l.action}</td>
                  <td className="p-3 text-muted-foreground">
                    {l.resource_type ? `${l.resource_type}:${l.resource_id || ''}` : '-'}
                  </td>
                  <td className="p-3">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      l.result === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
                      l.result === 'DENIED' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
                      'bg-destructive/20 text-destructive border border-destructive/40'
                    }`}>
                      {l.result}
                    </span>
                  </td>
                  <td className="p-3 text-muted-foreground">{l.ip_address || '127.0.0.1'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
