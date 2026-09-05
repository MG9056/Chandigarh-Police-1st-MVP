import React, { useState, useEffect } from 'react';
import { listInvestigations } from '../../api/investigationApi';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';
import { Plus, AlertCircle, RefreshCw } from 'lucide-react';

const PRIORITY_LABELS = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical' };
const PRIORITY_COLORS = {
  1: 'text-muted-foreground',
  2: 'text-yellow-400',
  3: 'text-orange-400',
  4: 'text-red-500 font-bold'
};
const STATUS_COLORS = {
  OPEN: 'text-blue-400',
  ACTIVE: 'text-yellow-400',
  CLOSED: 'text-green-400'
};

// Roles that can create an investigation
const CREATE_ROLES = ['SUPER ADMIN / DGP', 'IGP', 'SP', 'INSPECTOR', 'INVESTIGATOR'];

export default function InvestigationList({ onSelectInvestigation, onCreateClick }) {
  const { user } = useAuth();
  const [investigations, setInvestigations] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({ status: 'all', priority: 'all' });

  useEffect(() => {
    loadInvestigations();
  }, [filters]);

  const loadInvestigations = async () => {
    setLoading(true);
    setError('');
    try {
      const filterObj = {};
      if (filters.status !== 'all') filterObj.status = filters.status;
      if (filters.priority !== 'all') filterObj.priority = parseInt(filters.priority);
      const data = await listInvestigations(filterObj);
      setInvestigations(data.investigations || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const canCreate = CREATE_ROLES.includes(user?.role);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-primary font-mono tracking-wider uppercase">
            Investigations
          </h2>
          {!loading && (
            <p className="text-[10px] text-muted-foreground font-mono">
              {total} case{total !== 1 ? 's' : ''} on record
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={loadInvestigations} className="h-7 gap-1 text-xs">
            <RefreshCw className="w-3 h-3" />
          </Button>
          {canCreate && (
            <Button size="sm" onClick={onCreateClick} className="h-7 gap-1 text-xs">
              <Plus className="w-3 h-3" /> New Investigation
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          className="bg-background border border-border/60 rounded px-2 py-1 text-xs font-mono"
        >
          <option value="all">All Status</option>
          <option value="OPEN">Open</option>
          <option value="ACTIVE">Active</option>
          <option value="CLOSED">Closed</option>
        </select>
        <select
          value={filters.priority}
          onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
          className="bg-background border border-border/60 rounded px-2 py-1 text-xs font-mono"
        >
          <option value="all">All Priority</option>
          <option value="1">Low</option>
          <option value="2">Medium</option>
          <option value="3">High</option>
          <option value="4">Critical</option>
        </select>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="text-xs text-muted-foreground font-mono p-8 text-center animate-pulse">
          Loading investigations...
        </div>
      ) : investigations.length === 0 ? (
        <div className="text-xs text-muted-foreground font-mono p-8 text-center border border-dashed border-border/40 rounded">
          No investigations found.
          {canCreate && (
            <span
              className="text-primary cursor-pointer ml-1 hover:underline"
              onClick={onCreateClick}
            >
              Create one?
            </span>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {investigations.map((inv) => (
            <div
              key={inv.id}
              onClick={() => onSelectInvestigation(inv.investigation_id)}
              className="p-4 bg-card/40 border border-border/40 rounded cursor-pointer
                         hover:border-primary/50 hover:bg-card/60 transition-all duration-150
                         group"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  {/* Case Number + Status Badge */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono font-bold text-sm text-primary group-hover:text-primary/90">
                      {inv.investigation_id}
                    </span>
                    <span className={`text-[10px] font-mono uppercase tracking-wider ${STATUS_COLORS[inv.status] || 'text-foreground'}`}>
                      [{inv.status}]
                    </span>
                    <span className={`text-[10px] font-mono ${PRIORITY_COLORS[inv.priority]}`}>
                      P{inv.priority}:{PRIORITY_LABELS[inv.priority]}
                    </span>
                  </div>
                  {/* Title */}
                  <p className="text-xs text-foreground mt-1 truncate">{inv.title}</p>
                  {/* Meta row */}
                  <div className="flex gap-4 text-[10px] text-muted-foreground mt-1.5 font-mono">
                    {inv.unit && <span>Unit: {inv.unit}</span>}
                    <span>Lead: {inv.lead_investigator || 'Unassigned'}</span>
                    <span>{new Date(inv.created_at).toLocaleDateString('en-IN')}</span>
                  </div>
                </div>
                {/* Chevron hint */}
                <span className="text-muted-foreground text-xs opacity-0 group-hover:opacity-100 transition-opacity">›</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

