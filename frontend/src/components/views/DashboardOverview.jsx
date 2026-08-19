import { useTranslation } from 'react-i18next';
import { Activity, ShieldAlert, Network } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function DashboardOverview() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/dashboard/summary')
      .then(res => res.json())
      .then(data => setSummary(data))
      .catch(err => console.error("Error fetching summary:", err));
  }, []);

  if (!summary) return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading dashboard intelligence...</div>;

  return (
    <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      <h2 className="text-3xl font-bold mb-8 tracking-tight">{t('Welcome to DarKnight')}</h2>
      
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="p-5 rounded-xl border bg-card text-card-foreground shadow-sm flex flex-col gap-2 hover:shadow-md transition-shadow hover:border-blue-500/50">
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-500" /> {t('Active Investigations')}
          </span>
          <span className="text-4xl font-bold text-blue-500">{summary.active_investigations}</span>
        </div>
        <div className="p-5 rounded-xl border bg-card text-card-foreground shadow-sm flex flex-col gap-2 hover:shadow-md transition-shadow hover:border-red-500/50">
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-500" /> {t('Critical Alerts')}
          </span>
          <span className="text-4xl font-bold text-red-500">{summary.critical_alerts}</span>
        </div>
        <div className="p-5 rounded-xl border bg-card text-card-foreground shadow-sm flex flex-col gap-2 hover:shadow-md transition-shadow hover:border-green-500/50">
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Network className="w-4 h-4 text-green-500" /> {t('Sources Monitored')}
          </span>
          <span className="text-4xl font-bold text-green-500">{summary.sources_monitored}</span>
        </div>
      </div>
      
      <div className="p-6 rounded-xl border border-border/50 bg-muted/10 backdrop-blur-sm shadow-inner">
        <h3 className="text-xl font-semibold mb-3 tracking-tight">{t('Details')}</h3>
        <p className="text-muted-foreground leading-relaxed">
          {t('dashboard.detailsDescription')}
        </p>
        <p className="text-xs text-muted-foreground mt-4 text-right">
          Last Synced: {new Date(summary.last_update).toLocaleString()}
        </p>
      </div>
    </div>
  );
}
