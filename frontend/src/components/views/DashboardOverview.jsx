import { useTranslation } from 'react-i18next';
import { Activity, ShieldAlert, Network } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function DashboardOverview({ setActiveView }) {
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
      <h2 className="text-4xl font-black mb-10 tracking-widest uppercase text-foreground">{t('Welcome to DarKnight')}</h2>
      
      <div className="grid grid-cols-3 gap-6 mb-10">
        <div 
          onClick={() => setActiveView && setActiveView('search')}
          className="p-6 bracket-border bg-transparent flex flex-col gap-2 hover:bg-primary/5 transition-colors cursor-pointer group"
        >
          <span className="text-xs font-mono tracking-widest uppercase text-muted-foreground flex items-center gap-2 group-hover:text-primary transition-colors">
            <Activity className="w-4 h-4 text-primary" /> {t('Active Investigations')}
          </span>
          <span className="text-5xl font-black text-foreground mt-2">{summary.active_investigations}</span>
        </div>
        <div 
          onClick={() => setActiveView && setActiveView('alerts')}
          className="p-6 bracket-border bg-transparent flex flex-col gap-2 hover:bg-primary/5 transition-colors cursor-pointer group"
        >
          <span className="text-xs font-mono tracking-widest uppercase text-muted-foreground flex items-center gap-2 group-hover:text-primary transition-colors">
            <ShieldAlert className="w-4 h-4 text-primary" /> {t('Critical Alerts')}
          </span>
          <span className="text-5xl font-black text-foreground mt-2">{summary.critical_alerts}</span>
        </div>
        <div 
          onClick={() => setActiveView && setActiveView('data')}
          className="p-6 bracket-border bg-transparent flex flex-col gap-2 hover:bg-primary/5 transition-colors cursor-pointer group"
        >
          <span className="text-xs font-mono tracking-widest uppercase text-muted-foreground flex items-center gap-2 group-hover:text-primary transition-colors">
            <Network className="w-4 h-4 text-primary" /> {t('Sources Monitored')}
          </span>
          <span className="text-5xl font-black text-foreground mt-2">{summary.sources_monitored}</span>
        </div>
      </div>
      
      <div className="p-8 bracket-border bg-transparent relative">
        <h3 className="text-sm font-mono tracking-widest uppercase text-primary mb-4">{t('Details')}</h3>
        <p className="text-muted-foreground leading-relaxed text-lg font-light max-w-2xl">
          Select an item from the Navigation panel to view detailed metrics, suspect relationships, or actionable intelligence here. The dashboard automatically aggregates signals across multiple encrypted channels.
        </p>
        <p className="text-xs font-mono tracking-wider text-muted-foreground mt-8 text-right opacity-50 uppercase">
          Last Synced: {new Date(summary.last_update).toLocaleString()}
        </p>
      </div>
    </div>
  );
}
