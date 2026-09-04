import { KeyRound, Copy, Check, AlertTriangle, ShieldCheck, X } from 'lucide-react';
import { Button } from '../ui/button';
import React, { useState, useEffect, useRef } from 'react';
import QRCode from 'qrcode';

export default function TFAModal({ onClose, onComplete }) {
  const [step, setStep] = useState('init'); // init, verify
  const [setupData, setSetupData] = useState(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState('');
  const qrCanvasRef = useRef(null);

  const startSetup = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/2fa/setup', {
        method: 'POST',
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '2FA setup failed');
      setSetupData(data);
      setStep('verify');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
  if (setupData?.otpauth_url) {
    QRCode.toDataURL(setupData.otpauth_url, { width: 200, margin: 1 })
      .then(setQrDataUrl)
      .catch(err => console.error('QR generation failed:', err));
  }
  }, [setupData]);

  const handleVerify = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/2fa/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: verifyCode })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '2FA verification failed');
      onComplete();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyRecoveryCodes = () => {
    if (setupData?.recovery_codes) {
      navigator.clipboard.writeText(setupData.recovery_codes.join('\n'));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-card border border-border rounded-2xl p-6 shadow-2xl relative space-y-5 animate-in zoom-in-95">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 border-b border-border/40 pb-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500/20 text-amber-500 flex items-center justify-center">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-lg tracking-wider uppercase font-mono">Two-Factor Auth Setup</h3>
            <p className="text-xs text-muted-foreground font-mono">TOTP Authenticator Protection</p>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs font-mono rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {step === 'init' && (
          <div className="space-y-4 text-center py-4">
            <ShieldCheck className="w-12 h-12 text-amber-500 mx-auto" />
            <p className="text-xs text-muted-foreground font-mono leading-relaxed">
              Enhance your law-enforcement portal account with TOTP 2FA. You will need a standard authenticator app (Google Authenticator, Microsoft Authenticator, or Aegis).
            </p>
            <Button onClick={startSetup} disabled={loading} className="w-full font-mono gap-2">
              {loading ? 'Initializing...' : 'Generate 2FA Credentials'}
            </Button>
          </div>
        )}

        {step === 'verify' && setupData && (
          <div className="space-y-4">
            <div className="p-4 bg-muted/40 rounded-xl border border-border/60 space-y-2">
              {qrDataUrl && (
                <div className="flex flex-col items-center gap-2 p-4 bg-muted/40 rounded-xl border border-border/60">
                  <label className="text-xs font-mono uppercase text-muted-foreground">Scan with Authenticator App</label>
                  <img
                    src={qrDataUrl}
                    alt="2FA QR Code"
                    className="rounded-lg border border-border/60 bg-white p-2"
                    width={180}
                    height={180}
                  />
                  <p className="text-[10px] text-muted-foreground font-mono">or enter the key below manually</p>
                </div>
              )}
              <label className="text-xs font-mono uppercase text-muted-foreground block">Secret Key (Base32)</label>
              <div className="p-2 bg-background font-mono text-sm tracking-widest text-amber-400 font-bold rounded border select-all text-center">
                {setupData.secret}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-mono uppercase text-muted-foreground">One-Time Recovery Codes (Store Securely)</label>
                <Button variant="ghost" size="sm" onClick={copyRecoveryCodes} className="h-6 text-xs gap-1">
                  {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-1.5 p-2 bg-background rounded-lg border border-border/40 font-mono text-xs text-muted-foreground text-center">
                {setupData.recovery_codes.map((code, idx) => (
                  <span key={idx} className="p-1 bg-muted/30 rounded">{code}</span>
                ))}
              </div>
            </div>

            <form onSubmit={handleVerify} className="space-y-3 pt-2">
              <div className="space-y-1">
                <label className="text-xs font-mono uppercase text-muted-foreground">Enter 6-Digit Authenticator Code</label>
                <input
                  type="text"
                  required
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value)}
                  placeholder="000000"
                  className="w-full bg-background border border-border rounded-lg py-2 px-3 text-center text-lg font-mono tracking-widest focus:outline-none focus:border-amber-500"
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full font-mono gap-2">
                {loading ? 'Verifying...' : 'Verify & Activate 2FA'}
              </Button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
