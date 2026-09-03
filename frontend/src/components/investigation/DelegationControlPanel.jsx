import React, { useState, useEffect } from 'react';
import { UserCheck, ShieldPlus, ShieldMinus, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';

export default function DelegationControlPanel({ investigationId = 'INV-2026-001' }) {
  const { triggerReAuth } = useAuth();
  const [grants, setGrants] = useState([]);
  const [targetUserId, setTargetUserId] = useState('');
  const [expiresHours, setExpiresHours] = useState('72');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const fetchGrants = async () => {
    try {
      const res = await fetch(`/api/investigations/${investigationId}/grants`);
      if (res.ok) {
        const data = await res.json();
        setGrants(data);
      }
    } catch (e) {
      console.error('Failed to fetch grants:', e);
    }
  };

  useEffect(() => {
    fetchGrants();
  }, [investigationId]);

  const handleGrant = () => {
    if (!targetUserId) {
      setError('Please enter a valid Officer User ID');
      return;
    }
    setError('');
    setMsg('');

    triggerReAuth(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/investigations/${investigationId}/grant-access`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_user_id: parseInt(targetUserId),
            permission: 'MODIFY',
            expires_in_hours: parseInt(expiresHours)
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Grant failed');

        setMsg(data.message);
        setTargetUserId('');
        fetchGrants();
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    });
  };

  const handleRevoke = (grantId) => {
    setError('');
    setMsg('');

    triggerReAuth(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/investigations/${investigationId}/revoke-access`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ grant_id: grantId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Revocation failed');

        setMsg(data.message);
        fetchGrants();
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    });
  };

  return (
    <div className="p-5 rounded-xl border border-border/60 bg-card space-y-4 font-mono">
      <div className="flex items-center justify-between border-b border-border/40 pb-3">
        <div>
          <h4 className="font-bold text-sm text-foreground flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-primary" /> Delegated Investigation Access
          </h4>
          <p className="text-xs text-muted-foreground">
            Explicitly grant modification authority for Investigation <span className="text-primary font-bold">{investigationId}</span>
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={fetchGrants}>
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {msg && (
        <div className="p-3 bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 text-xs rounded-lg flex items-center gap-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{msg}</span>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        <input
          type="number"
          value={targetUserId}
          onChange={(e) => setTargetUserId(e.target.value)}
          placeholder="Officer User ID"
          className="bg-background border border-border/60 rounded px-3 py-1.5 text-xs focus:border-primary"
        />
        <select
          value={expiresHours}
          onChange={(e) => setExpiresHours(e.target.value)}
          className="bg-background border border-border/60 rounded px-3 py-1.5 text-xs focus:border-primary"
        >
          <option value="24">Expire in 24 Hours</option>
          <option value="72">Expire in 72 Hours</option>
          <option value="168">Expire in 7 Days</option>
        </select>
        <Button size="sm" onClick={handleGrant} disabled={loading} className="gap-1 text-xs">
          <ShieldPlus className="w-4 h-4" /> Grant Access
        </Button>
      </div>

      <div className="space-y-2 pt-2">
        <label className="text-xs uppercase text-muted-foreground block">Active Modification Grants</label>
        {grants.length === 0 ? (
          <div className="text-xs text-muted-foreground p-3 border border-dashed rounded text-center">
            No active explicit access grants for this investigation.
          </div>
        ) : (
          <div className="space-y-1.5">
            {grants.map((g) => (
              <div key={g.id} className="p-2.5 bg-muted/30 border border-border/40 rounded flex items-center justify-between text-xs">
                <div>
                  <span className="font-bold text-foreground">Officer User ID #{g.user_id}</span>
                  <span className="text-muted-foreground text-[10px] block">
                    Granted by Officer #{g.granted_by} | Expires: {g.expires_at ? new Date(g.expires_at).toLocaleString() : 'Never'}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleRevoke(g.id)}
                  className="h-6 text-[11px] border-destructive/50 text-destructive hover:bg-destructive/10 gap-1"
                >
                  <ShieldMinus className="w-3 h-3" /> Revoke
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
