import React, { useState, useEffect } from 'react';
import {
  getInvestigation,
  updateInvestigation,
  closeInvestigation,
  assignInvestigator,
  removeAssignment
} from '../../api/investigationApi';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';
import { AlertCircle, CheckCircle, Edit2, Save, X, UserPlus, Trash2, ArrowLeft } from 'lucide-react';

const PRIORITY_LABELS = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical' };
const STATUS_COLORS = {
  OPEN: 'text-blue-400',
  ACTIVE: 'text-yellow-400',
  CLOSED: 'text-green-400'
};

export default function InvestigationDetail({ investigationId, onBack }) {
  const { user, triggerReAuth } = useAuth();
  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({});
  const [assignmentMode, setAssignmentMode] = useState(false);
  const [newAssigneeId, setNewAssigneeId] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    loadInvestigation();
  }, [investigationId]);

  const loadInvestigation = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getInvestigation(investigationId);
      setInvestigation(data);
      setFormData({
        title: data.title,
        description: data.description || '',
        case_type: data.case_type || '',
        status: data.status,
        priority: data.priority,
        unit: data.unit || ''
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const showSuccess = (msg) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 3500);
  };

  const handleSave = async () => {
    setActionLoading(true);
    setError('');
    try {
      // Only send changed / non-empty fields
      const payload = {};
      if (formData.title !== investigation.title) payload.title = formData.title;
      if (formData.description !== (investigation.description || '')) payload.description = formData.description;
      if (formData.case_type !== (investigation.case_type || '')) payload.case_type = formData.case_type;
      if (formData.status !== investigation.status) payload.status = formData.status;
      if (formData.priority !== investigation.priority) payload.priority = formData.priority;
      if (formData.unit !== (investigation.unit || '')) payload.unit = formData.unit;

      if (Object.keys(payload).length === 0) {
        setEditMode(false);
        return;
      }
      await updateInvestigation(investigationId, payload);
      showSuccess('Investigation updated successfully');
      setEditMode(false);
      loadInvestigation();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleClose = () => {
    const reason = window.prompt('Enter closure reason (required):');
    if (!reason || !reason.trim()) return;

    triggerReAuth(async () => {
      setActionLoading(true);
      setError('');
      try {
        await closeInvestigation(investigationId, { closure_reason: reason.trim(), closure_notes: '' });
        showSuccess('Investigation closed successfully');
        loadInvestigation();
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(false);
      }
    });
  };

  const handleAssign = () => {
    const idNum = parseInt(newAssigneeId);
    if (!idNum || isNaN(idNum)) {
      setError('Please enter a valid numeric user ID');
      return;
    }

    triggerReAuth(async () => {
      setActionLoading(true);
      setError('');
      try {
        await assignInvestigator(investigationId, idNum);
        showSuccess('Investigator assigned successfully');
        setNewAssigneeId('');
        setAssignmentMode(false);
        loadInvestigation();
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(false);
      }
    });
  };

  const handleRemoveAssignment = (assignmentId, email) => {
    if (!window.confirm(`Remove ${email} from this investigation?`)) return;

    triggerReAuth(async () => {
      setActionLoading(true);
      setError('');
      try {
        await removeAssignment(investigationId, assignmentId);
        showSuccess('Investigator removed successfully');
        loadInvestigation();
      } catch (err) {
        setError(err.message);
      } finally {
        setActionLoading(false);
      }
    });
  };

  if (loading) {
    return (
      <div className="text-xs text-muted-foreground font-mono p-8 text-center animate-pulse">
        Loading investigation...
      </div>
    );
  }

  if (!investigation) {
    return (
      <div className="text-destructive text-xs font-mono p-8 text-center">
        {error || 'Investigation not found'}
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-bold text-primary font-mono">{investigation.investigation_id}</h2>
            <span className={`text-xs font-mono uppercase tracking-wider ${STATUS_COLORS[investigation.status] || ''}`}>
              [{investigation.status}]
            </span>
          </div>
          <p className="text-sm text-foreground mt-0.5">{investigation.title}</p>
        </div>
        <Button size="sm" variant="ghost" onClick={onBack} className="h-7 gap-1 text-xs flex-shrink-0">
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

      {/* Details Card */}
      <div className="p-4 bg-card/40 border border-border/50 rounded space-y-3">
        <div className="flex items-center justify-between border-b border-border/40 pb-2">
          <h3 className="font-bold text-sm font-mono uppercase tracking-wider text-muted-foreground">Details</h3>
          {investigation.can_edit && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => { setEditMode(!editMode); setError(''); }}
              className="h-6 gap-1 text-xs"
            >
              {editMode ? <X className="w-3 h-3" /> : <Edit2 className="w-3 h-3" />}
              {editMode ? 'Cancel' : 'Edit'}
            </Button>
          )}
        </div>

        {editMode ? (
          <div className="space-y-2">
            <div>
              <label className="text-[10px] text-muted-foreground font-mono uppercase">Title</label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full mt-0.5 bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground font-mono uppercase">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full mt-0.5 bg-background border border-border/60 rounded px-2 py-1.5 text-xs h-16 resize-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-muted-foreground font-mono uppercase">Status</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full mt-0.5 bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
                >
                  <option value="OPEN">Open</option>
                  <option value="ACTIVE">Active</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground font-mono uppercase">Priority</label>
                <select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                  className="w-full mt-0.5 bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
                >
                  <option value={1}>Low</option>
                  <option value={2}>Medium</option>
                  <option value={3}>High</option>
                  <option value={4}>Critical</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground font-mono uppercase">Case Type</label>
              <input
                type="text"
                value={formData.case_type}
                onChange={(e) => setFormData({ ...formData, case_type: e.target.value })}
                placeholder="E.g., Drug Trafficking"
                className="w-full mt-0.5 bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground font-mono uppercase">Unit / Jurisdiction</label>
              <input
                type="text"
                value={formData.unit}
                onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                placeholder="E.g., Cyber Crime Cell"
                className="w-full mt-0.5 bg-background border border-border/60 rounded px-2 py-1.5 text-xs"
              />
            </div>
            <Button size="sm" onClick={handleSave} disabled={actionLoading} className="gap-1 text-xs">
              <Save className="w-3 h-3" /> Save Changes
            </Button>
          </div>
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs font-mono">
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Status</dt>
              <dd className={STATUS_COLORS[investigation.status]}>{investigation.status}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Priority</dt>
              <dd>{PRIORITY_LABELS[investigation.priority] || investigation.priority}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Case Type</dt>
              <dd>{investigation.case_type || '—'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Unit</dt>
              <dd>{investigation.unit || '—'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Lead Investigator</dt>
              <dd>{investigation.lead_investigator_email || 'Unassigned'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Created By</dt>
              <dd>{investigation.created_by_email || '—'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Opened</dt>
              <dd>{new Date(investigation.created_at).toLocaleString('en-IN')}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-[10px] uppercase">Last Updated</dt>
              <dd>{new Date(investigation.updated_at).toLocaleString('en-IN')}</dd>
            </div>
            {investigation.description && (
              <div className="col-span-2">
                <dt className="text-muted-foreground text-[10px] uppercase">Description</dt>
                <dd className="text-foreground">{investigation.description}</dd>
              </div>
            )}
            {investigation.status === 'CLOSED' && (
              <>
                <div>
                  <dt className="text-muted-foreground text-[10px] uppercase">Closed At</dt>
                  <dd>{investigation.closed_at ? new Date(investigation.closed_at).toLocaleString('en-IN') : '—'}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-[10px] uppercase">Closure Reason</dt>
                  <dd>{investigation.closure_reason || '—'}</dd>
                </div>
                {investigation.closure_notes && (
                  <div className="col-span-2">
                    <dt className="text-muted-foreground text-[10px] uppercase">Closure Notes</dt>
                    <dd>{investigation.closure_notes}</dd>
                  </div>
                )}
              </>
            )}
          </dl>
        )}
      </div>

      {/* Assignments Card */}
      <div className="p-4 bg-card/40 border border-border/50 rounded space-y-3">
        <div className="flex items-center justify-between border-b border-border/40 pb-2">
          <h3 className="font-bold text-sm font-mono uppercase tracking-wider text-muted-foreground">
            Assigned Investigators
          </h3>
          {investigation.can_assign && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => { setAssignmentMode(!assignmentMode); setError(''); }}
              className="h-6 gap-1 text-xs"
            >
              <UserPlus className="w-3 h-3" /> {assignmentMode ? 'Cancel' : 'Assign'}
            </Button>
          )}
        </div>

        {assignmentMode && (
          <div className="flex gap-2 items-center">
            <input
              type="number"
              value={newAssigneeId}
              onChange={(e) => setNewAssigneeId(e.target.value)}
              placeholder="User ID"
              className="flex-1 bg-background border border-border/60 rounded px-2 py-1.5 text-xs font-mono"
              onKeyDown={(e) => e.key === 'Enter' && handleAssign()}
            />
            <Button size="sm" onClick={handleAssign} disabled={actionLoading} className="text-xs">
              Assign
            </Button>
          </div>
        )}

        {investigation.assignments.length === 0 ? (
          <p className="text-xs text-muted-foreground font-mono">No investigators assigned.</p>
        ) : (
          <div className="space-y-1.5">
            {investigation.assignments.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between text-xs bg-muted/20 border border-border/30 p-2 rounded font-mono"
              >
                <div>
                  <span className="text-foreground">{a.assigned_to_email}</span>
                  <span className="text-muted-foreground ml-2 text-[10px]">
                    by {a.assigned_by_email} on {new Date(a.assigned_at).toLocaleDateString('en-IN')}
                  </span>
                </div>
                {investigation.can_assign && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleRemoveAssignment(a.id, a.assigned_to_email)}
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

      {/* Close Investigation */}
      {investigation.status !== 'CLOSED' && investigation.can_edit && (
        <div className="flex items-center justify-end pt-2 border-t border-border/30">
          <Button
            size="sm"
            variant="outline"
            onClick={handleClose}
            disabled={actionLoading}
            className="text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
          >
            Close Investigation
          </Button>
        </div>
      )}
    </div>
  );
}

