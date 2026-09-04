import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Server, Database, Globe, RefreshCcw, MessageSquare, Radio } from 'lucide-react';
import { Button } from '../ui/button';
import { apiFetch } from '../../lib/apiClient';

const defaultSources = [
  { id: 1, name: "Darknet Market Alpha", type: "Onion Service", status: "Active", lastSync: "2 mins ago" },
  { id: 2, name: "Encrypted Forum Z", type: "P2P Forum", status: "Syncing", lastSync: "In Progress" },
  { id: 3, name: "BTC Blockchain Node", type: "Ledger", status: "Active", lastSync: "Just now" },
  { id: 4, name: "Public Telegram Group A", type: "Social", status: "Offline", lastSync: "2 days ago" },
  { id: 5, name: "Monero Network Crawler", type: "P2P Crawler", status: "Active", lastSync: "5 mins ago" },
  { id: 6, name: "Signal Channel Aggregator", type: "Messaging", status: "Active", lastSync: "10 mins ago" }
];

export default function DataCollectionStatus() {
  const { t } = useTranslation();
  const [sources, setSources] = useState(defaultSources);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
  apiFetch('/api/data-sources')
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (Array.isArray(data) && data.length > 0) {
        setSources(data);
      }
    })
    .catch(err => console.error("Error fetching data sources:", err))
    .finally(() => setLoading(false));
}, []);

  const getSourceIcon = (type) => {
    switch (type) {
      case 'Onion Service': return <Globe className="w-5 h-5 text-purple-500" />;
      case 'P2P Forum': return <Database className="w-5 h-5 text-blue-500 animate-pulse" />;
      case 'Ledger': return <Server className="w-5 h-5 text-yellow-500" />;
      case 'Social': return <Globe className="w-5 h-5 text-red-500" />;
      case 'P2P Crawler': return <Radio className="w-5 h-5 text-green-500 animate-pulse" />;
      case 'Messaging': return <MessageSquare className="w-5 h-5 text-cyan-500" />;
      default: return <Globe className="w-5 h-5 text-primary" />;
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full font-mono">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold tracking-tight mb-2 uppercase">{t('Multi-Source Data Collection')}</h2>
          <p className="text-muted-foreground text-xs">{t('Monitor the aggregation of intelligence from legally accessible digital platforms.')}</p>
        </div>
        <Button variant="outline" className="gap-2 font-mono text-xs">
          <RefreshCcw className="w-4 h-4" /> {t('Restart All Nodes')}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {sources.map((src, i) => (
          <div key={src.id || i} className="p-5 rounded-xl border bg-card hover:bg-muted/30 transition-colors">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                {getSourceIcon(src.type)}
                <div>
                  <h4 className="font-semibold text-sm">{t(src.name) || src.name}</h4>
                  <span className="text-[11px] text-muted-foreground uppercase tracking-wider">{t(src.type) || src.type}</span>
                </div>
              </div>
              <span className={`px-2 py-1 rounded text-xs font-semibold ${
                src.status === 'Active' ? 'bg-green-500/20 text-green-500' :
                src.status === 'Syncing' ? 'bg-blue-500/20 text-blue-500' :
                'bg-red-500/20 text-red-500'
              }`}>
                {t(src.status) || src.status}
              </span>
            </div>
            
            <div className="w-full bg-muted rounded-full h-1.5 mb-2 overflow-hidden">
              <div className={`h-1.5 rounded-full ${src.status === 'Offline' ? 'bg-red-500 w-full opacity-50' : src.status === 'Syncing' ? 'bg-blue-500 w-2/3 animate-pulse' : 'bg-green-500 w-full'}`}></div>
            </div>
            <p className="text-xs text-muted-foreground text-right">{t('Last Sync')}: {t(src.lastSync) || src.lastSync}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
