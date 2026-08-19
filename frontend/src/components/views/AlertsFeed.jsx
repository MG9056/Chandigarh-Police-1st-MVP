import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, TrendingUp, Key } from 'lucide-react';

export default function AlertsFeed() {
  const { t } = useTranslation();
  const [alerts, setAlerts] = useState([]);
  const [suspicious, setSuspicious] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/alerts')
      .then(res => res.json())
      .then(data => setAlerts(data));
      
    fetch('http://localhost:8000/api/alerts/suspicious')
      .then(res => res.json())
      .then(data => setSuspicious(data));
  }, []);

  const getSeverityColor = (severity) => {
    if (severity === 'red') return 'bg-red-500/10 border-red-500/20 text-red-500';
    if (severity === 'yellow') return 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500';
    return 'bg-green-500/10 border-green-500/20 text-green-500';
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">{t('Automated Alert Generation')}</h2>
        <p className="text-muted-foreground mb-4">{t('Real-time notifications for predefined risk indicators across monitored sources.')}</p>
        
        <div className="space-y-3">
          {alerts.map(alert => (
            <div key={alert.id} className={`p-4 rounded-xl border flex items-start gap-4 ${getSeverityColor(alert.severity)}`}>
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">{alert.message}</p>
                <p className="text-xs opacity-80 mt-1">{new Date(alert.timestamp).toLocaleString()}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-2 mt-8">{t('Suspicious Activity Detection')}</h2>
        <p className="text-muted-foreground mb-4">{t('AI-driven detection of abnormal behavioral trends and recurring keywords.')}</p>
        
        <div className="grid gap-4">
          {suspicious.map(act => (
            <div key={act.id} className="p-4 rounded-xl border bg-card text-card-foreground shadow-sm flex items-start gap-4">
              {act.type === 'keyword_match' ? <Key className="w-5 h-5 text-orange-500 mt-0.5" /> : <TrendingUp className="w-5 h-5 text-purple-500 mt-0.5" />}
              <div className="flex-1">
                <div className="flex justify-between items-start">
                  <p className="font-semibold">{act.description}</p>
                  <span className="text-xs font-mono bg-muted px-2 py-1 rounded">Confidence: {(act.confidence * 100).toFixed(0)}%</span>
                </div>
                <p className="text-sm text-muted-foreground mt-1 capitalize">Trigger Type: {act.type.replace('_', ' ')}</p>
                <p className="text-xs text-muted-foreground mt-1">Detected on: {act.date}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
