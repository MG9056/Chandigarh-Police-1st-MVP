import React, { useState } from 'react';
import { Shield, Lock, Mail, User, ShieldCheck, AlertTriangle, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';

export default function RegisterPage({ onSwitchToLogin }) {
  const { signup } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    badge_number: '',
    unit: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (formData.password.length < 12) {
      setError('Password must be at least 12 characters long');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      const res = await signup({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        badge_number: formData.badge_number,
        unit: formData.unit
      });
      setSuccessMsg(res.message || 'Account registration submitted. Pending senior officer review.');
    } catch (err) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-background text-foreground flex items-center justify-center p-4 relative z-10">
      <div className="w-full max-w-lg bg-card/80 backdrop-blur-xl border border-border/60 rounded-2xl p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-border/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/15 border border-primary/40 flex items-center justify-center text-primary">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-wider text-primary uppercase font-mono">
                Account Registration
              </h2>
              <p className="text-xs text-muted-foreground font-mono">Chandigarh Police Intelligence Portal</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onSwitchToLogin} className="gap-1 font-mono text-xs">
            <ArrowLeft className="w-4 h-4" /> Back to Login
          </Button>
        </div>

        {successMsg ? (
          <div className="p-6 bg-emerald-500/15 border border-emerald-500/40 rounded-xl space-y-4 text-center animate-in fade-in">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
            <h3 className="text-lg font-bold text-emerald-400 font-mono">Request Submitted Successfully</h3>
            <p className="text-xs text-muted-foreground font-mono leading-relaxed">
              {successMsg}
            </p>
            <Button onClick={onSwitchToLogin} className="w-full font-mono">
              Return to Login Screen
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs font-mono rounded-lg flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Full Name *</label>
                <input
                  type="text"
                  name="full_name"
                  required
                  value={formData.full_name}
                  onChange={handleChange}
                  placeholder="Officer Full Name"
                  className="w-full bg-background/60 border border-border/60 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-primary font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Badge Number</label>
                <input
                  type="text"
                  name="badge_number"
                  value={formData.badge_number}
                  onChange={handleChange}
                  placeholder="e.g. CP-4491"
                  className="w-full bg-background/60 border border-border/60 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-primary font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Official Email *</label>
                <input
                  type="email"
                  name="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="officer@chandigarhpolice.gov.in"
                  className="w-full bg-background/60 border border-border/60 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-primary font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Assigned Unit</label>
                <input
                  type="text"
                  name="unit"
                  value={formData.unit}
                  onChange={handleChange}
                  placeholder="Cyber Crime Cell / Special Task Force"
                  className="w-full bg-background/60 border border-border/60 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-primary font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Password (Min 12 Chars) *</label>
                <input
                  type="password"
                  name="password"
                  required
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="••••••••••••"
                  className="w-full bg-background/60 border border-border/60 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-primary font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Confirm Password *</label>
                <input
                  type="password"
                  name="confirmPassword"
                  required
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  placeholder="••••••••••••"
                  className="w-full bg-background/60 border border-border/60 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-primary font-mono"
                />
              </div>
            </div>

            <div className="p-3 bg-muted/30 border border-border/40 rounded-lg text-xs font-mono text-muted-foreground">
              ℹ️ Role assignment and operational scope will be determined and assigned by a Senior Officer during account review.
            </div>

            <Button type="submit" disabled={loading} className="w-full gap-2 mt-4 font-mono">
              {loading ? 'Submitting Request...' : 'Submit Operational Registration'}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
