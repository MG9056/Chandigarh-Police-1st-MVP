import React, { useState } from 'react';
import { Lock, ShieldAlert, X, ArrowRight, AlertTriangle } from 'lucide-react';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';

export default function ReAuthModal() {
  const { reAuthRequired, handleReAuthSuccess, cancelReAuth } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!reAuthRequired) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/auth/reauthenticate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Re-authentication failed');

      setPassword('');
      handleReAuthSuccess();
    } catch (err) {
      setError(err.message || 'Incorrect password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-card border border-amber-500/50 rounded-2xl p-6 shadow-2xl relative space-y-4 animate-in zoom-in-95 font-mono">
        <button
          onClick={cancelReAuth}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 border-b border-border/40 pb-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500/20 text-amber-500 flex items-center justify-center border border-amber-500/40">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-base uppercase text-amber-400">Security Confirmation Required</h3>
            <p className="text-xs text-muted-foreground">High-Risk Sensitive Operation</p>
          </div>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          For operational security, please confirm your identity by re-entering your account password before proceeding.
        </p>

        {error && (
          <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs uppercase text-muted-foreground">Account Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="password"
                required
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-background border border-border/60 rounded-lg py-2 pl-9 pr-3 text-sm focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={cancelReAuth} className="flex-1 text-xs">
              Cancel
            </Button>
            <Button type="submit" disabled={loading} className="flex-1 text-xs gap-1 bg-amber-600 hover:bg-amber-700 text-white">
              {loading ? 'Verifying...' : 'Authorize Action'} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
