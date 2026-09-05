import React, { useState } from 'react';
import { createInvestigation } from '../../api/investigationApi';
import { Button } from '../ui/button';
import { AlertCircle, CheckCircle, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function InvestigationCreate({ onSuccess, onCancel }) {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    investigation_id: '',
    title: '',
    description: '',
    case_type: '',
    priority: 2,
    status: 'OPEN',
    unit: user?.unit || ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!formData.investigation_id.trim()) {
      setError('Investigation ID is required');
      return;
    }
    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await createInvestigation({
        ...formData,
        investigation_id: formData.investigation_id.trim(),
        title: formData.title.trim(),
        description: formData.description.trim() || null,
        case_type: formData.case_type.trim() || null,
        unit: formData.unit.trim() || null
      });
      setSuccess('Investigation created successfully!');
      setTimeout(() => onSuccess(), 1200);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-background border border-border/60 rounded-lg p-6 w-full max-w-md space-y-4 shadow-xl">
        {/* Modal Header */}
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-base font-mono tracking-wider uppercase text-primary">
            New Investigation
          </h2>
          <Button size="sm" variant="ghost" onClick={onCancel} className="h-7 w-7 p-0">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Feedback */}
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

        {/* Form Fields */}
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-mono uppercase text-muted-foreground">
              Investigation ID <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={formData.investigation_id}
              onChange={(e) => setFormData({ ...formData, investigation_id: e.target.value.toUpperCase() })}
              placeholder="E.g., INV-2026-042"
              className="w-full mt-1 bg-card border border-border/60 rounded px-3 py-2 text-xs font-mono"
            />
          </div>

          <div>
            <label className="text-[10px] font-mono uppercase text-muted-foreground">
              Title <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="Brief descriptive title"
              className="w-full mt-1 bg-card border border-border/60 rounded px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label className="text-[10px] font-mono uppercase text-muted-foreground">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Scope, initial intelligence, objectives..."
              className="w-full mt-1 bg-card border border-border/60 rounded px-3 py-2 text-xs h-16 resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase text-muted-foreground">Case Type</label>
              <input
                type="text"
                value={formData.case_type}
                onChange={(e) => setFormData({ ...formData, case_type: e.target.value })}
                placeholder="E.g., Drug Trafficking"
                className="w-full mt-1 bg-card border border-border/60 rounded px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase text-muted-foreground">Priority</label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                className="w-full mt-1 bg-card border border-border/60 rounded px-3 py-2 text-xs"
              >
                <option value={1}>1 — Low</option>
                <option value={2}>2 — Medium</option>
                <option value={3}>3 — High</option>
                <option value={4}>4 — Critical</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-mono uppercase text-muted-foreground">Unit / Jurisdiction</label>
            <input
              type="text"
              value={formData.unit}
              onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
              placeholder="E.g., Cyber Crime Cell, Chandigarh"
              className="w-full mt-1 bg-card border border-border/60 rounded px-3 py-2 text-xs"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-2">
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={loading || !!success}
            className="flex-1 text-xs"
          >
            {loading ? 'Creating...' : 'Create Investigation'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 text-xs"
          >
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}

