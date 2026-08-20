import { Server, Database, Globe, RefreshCcw } from 'lucide-react';
import { Button } from '../ui/button';
import { useTranslation } from 'react-i18next';

export default function DataCollectionStatus() {
  const { t } = useTranslation();
  const sources = [
    { name: "Darknet Market Alpha", type: "Onion Service", status: "Active", lastSync: "2 mins ago", icon: <Globe className="w-5 h-5 text-purple-500" /> },
    { name: "Encrypted Forum Z", type: "P2P Forum", status: "Syncing", lastSync: "In Progress", icon: <Database className="w-5 h-5 text-blue-500 animate-pulse" /> },
    { name: t("Darknet Market Alpha"), type: t("Onion Service"), status: t("Active"), lastSync: t("2 mins ago"), icon: <Globe className="w-5 h-5 text-purple-500" /> },
    { name: t("Encrypted Forum Z"), type: t("P2P Forum"), status: t("Syncing"), lastSync: t("In Progress"), icon: <Database className="w-5 h-5 text-blue-500 animate-pulse" /> },
    { name: t("BTC Blockchain Node"), type: t("Ledger"), status: t("Active"), lastSync: t("Just now"), icon: <Server className="w-5 h-5 text-yellow-500" /> },
    { name: t("Public Telegram Group A"), type: t("Social"), status: t("Offline"), lastSync: t("2 days ago"), icon: <Globe className="w-5 h-5 text-red-500" /> },
  ];

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full">
      <div className="mb-4 flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold tracking-tight mb-2">{t('Multi-Source Data Collection')}</h2>
          <p className="text-muted-foreground">{t('Monitor the aggregation of intelligence from legally accessible digital platforms.')}</p>
        </div>
        <Button variant="outline" className="gap-2">
          <RefreshCcw className="w-4 h-4" /> {t('Restart All Nodes')}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {sources.map((src, i) => (
          <div key={i} className="p-5 rounded-xl border bg-card hover:bg-muted/30 transition-colors">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                {src.icon}
                <div>
                  <h4 className="font-semibold">{src.name}</h4>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">{src.type}</span>
                </div>
              </div>
              <span className={`px-2 py-1 rounded text-xs font-semibold ${
                src.status === 'Active' ? 'bg-green-500/20 text-green-500' :
                src.status === 'Syncing' ? 'bg-blue-500/20 text-blue-500' :
                'bg-red-500/20 text-red-500'
              }`}>
                {src.status}
              </span>
            </div>
            
            <div className="w-full bg-muted rounded-full h-1.5 mb-2 overflow-hidden">
              <div className={`h-1.5 rounded-full ${src.status === 'Offline' ? 'bg-red-500 w-full opacity-50' : src.status === 'Syncing' ? 'bg-blue-500 w-2/3 animate-pulse' : 'bg-green-500 w-full'}`}></div>
            </div>
            <p className="text-xs text-muted-foreground text-right">Last Sync: {src.lastSync}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
