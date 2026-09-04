import React, { useState } from 'react';
import { Shield, Lock, Mail, KeyRound, AlertTriangle, ArrowRight } from 'lucide-react';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';

export default function LoginPage({ onSwitchToRegister }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [mfaRequired, setMfaRequired] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password, totpCode);
    } catch (err) {
      if (err.message === 'MFA_REQUIRED') {
        setMfaRequired(true);
        setError('Two-Factor Authentication code required');
      } else {
        setError(err.message || 'Authentication failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-background text-foreground flex items-center justify-center p-4 relative z-10">
      {/* Background glow effects */}
      <div className="absolute inset-0 pointer-events-none z-[-1] overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-primary/10 rounded-full blur-[160px]" />
      </div>

      <div className="w-full max-w-md bg-card/80 backdrop-blur-xl border border-border/60 rounded-2xl p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="w-12 h-12 rounded-xl bg-primary/15 border border-primary/40 flex items-center justify-center text-primary mb-1">
            <Shield className="w-6 h-6 text-glow" />
          </div>
          <h1 className="text-2xl font-bold tracking-[0.15em] text-primary text-glow uppercase">
            DarKnight
          </h1>
          <p className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Chandigarh Police Law Enforcement Intelligence
          </p>
        </div>

        {error && (
          <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs font-mono rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-mono uppercase text-muted-foreground">Official Email</label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="officer@chandigarhpolice.gov.in"
                className="w-full bg-background/60 border border-border/60 rounded-lg py-2 pl-9 pr-3 text-sm focus:outline-none focus:border-primary font-mono placeholder:text-muted-foreground/50"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-mono uppercase text-muted-foreground">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-background/60 border border-border/60 rounded-lg py-2 pl-9 pr-3 text-sm focus:outline-none focus:border-primary font-mono placeholder:text-muted-foreground/50"
              />
            </div>
          </div>

          {mfaRequired && (
            <div className="space-y-1 animate-in fade-in slide-in-from-top-2">
              <label className="text-xs font-mono uppercase text-amber-500 font-semibold">2FA Authenticator Code</label>
              <div className="relative">
                <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-amber-500" />
                <input
                  type="text"
                  required
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  placeholder="6-digit code or recovery code"
                  className="w-full bg-background/60 border border-amber-500/60 rounded-lg py-2 pl-9 pr-3 text-sm focus:outline-none focus:border-amber-500 font-mono tracking-widest"
                />
              </div>
            </div>
          )}

          <Button type="submit" disabled={loading} className="w-full gap-2 mt-2">
            {loading ? 'Authenticating...' : (
              <>
                <span>Sign In to Terminal</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </Button>
        </form>

        <div className="border-t border-border/40 pt-4 text-center">
          <p className="text-xs text-muted-foreground">
            Don't have an operational account?{' '}
            <button
              type="button"
              onClick={onSwitchToRegister}
              className="text-primary hover:underline font-semibold font-mono"
            >
              Request Access
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
