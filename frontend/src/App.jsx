import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ThemeProvider, useTheme } from './components/theme-provider';
import BootupAnimation from './components/BootupAnimation';
import { Button } from './components/ui/button';
import { Activity, Bell, Network, Search, FileText, ShieldAlert, Database, Shield } from 'lucide-react';

import DashboardOverview from './components/views/DashboardOverview';
import NetworkGraph from './components/views/NetworkGraph';
import AlertsFeed from './components/views/AlertsFeed';
import SearchInvestigation from './components/views/SearchInvestigation';
import DataCollectionStatus from './components/views/DataCollectionStatus';
import ReportingEvidence from './components/views/ReportingEvidence';
import AccessControl from './components/views/AccessControl';

function Dashboard() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [activeView, setActiveView] = useState('dashboard');

  const changeLang = (lang) => {
    i18n.changeLanguage(lang);
  };

  const renderActiveView = () => {
    switch (activeView) {
      case 'dashboard': return <DashboardOverview />;
      case 'data': return <DataCollectionStatus />;
      case 'alerts': return <AlertsFeed />;
      case 'network': return <NetworkGraph />;
      case 'search': return <SearchInvestigation />;
      case 'reports': return <ReportingEvidence />;
      case 'security': return <AccessControl />;
      default: return <DashboardOverview />;
    }
  };

  const navItems = [
    { id: 'dashboard', icon: <Activity className="w-5 h-5 text-blue-500" />, label: 'Dashboard' },
    { id: 'data', icon: <Database className="w-5 h-5 text-indigo-500" />, label: 'Data Collection Status' },
    { id: 'alerts', icon: <Bell className="w-5 h-5 text-yellow-500" />, label: 'Alerts & Suspicious Activity' },
    { id: 'network', icon: <Network className="w-5 h-5 text-purple-500" />, label: 'Network Visualization' },
    { id: 'search', icon: <Search className="w-5 h-5 text-orange-500" />, label: 'Search & Investigation' },
    { id: 'reports', icon: <FileText className="w-5 h-5 text-green-500" />, label: 'Reports & Evidence' },
    { id: 'security', icon: <Shield className="w-5 h-5 text-red-500" />, label: 'Security & Access Control' },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">
      {/* Header / Top Nav */}
      <header className="h-16 border-b border-border flex items-center justify-between px-6 bg-card text-card-foreground shadow-sm">
        <div className="flex items-center gap-3">
          <img src="/cdg-logo.png" alt="Logo" className="w-8 h-8" />
          <h1 className="text-xl font-bold tracking-tight text-blue-600 dark:text-blue-400">DarKnight</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex bg-muted/50 p-1 rounded-md border border-border/50">
            <Button variant={i18n.language === 'en' ? 'default' : 'ghost'} size="sm" onClick={() => changeLang('en')} className="h-7 text-xs px-2">EN</Button>
            <Button variant={i18n.language === 'hi' ? 'default' : 'ghost'} size="sm" onClick={() => changeLang('hi')} className="h-7 text-xs px-2">HI</Button>
            <Button variant={i18n.language === 'pa' ? 'default' : 'ghost'} size="sm" onClick={() => changeLang('pa')} className="h-7 text-xs px-2">PA</Button>
          </div>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </Button>
        </div>
      </header>

      {/* Main Layout */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left Panel: Navigation */}
        <aside className="w-[280px] border-r border-border bg-muted/20 p-4 overflow-y-auto flex-shrink-0">
          <h2 className="text-lg font-semibold mb-4 text-primary tracking-tight">{t('General Info')}</h2>
          <div className="space-y-2">
            {navItems.map(item => (
              <div 
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={`flex items-center gap-3 p-3 rounded-md border shadow-sm transition-all cursor-pointer ${
                  activeView === item.id 
                  ? 'bg-primary/10 border-primary shadow-md' 
                  : 'bg-card border-border/50 hover:border-primary/50 hover:bg-muted/50'
                }`}
              >
                {item.icon}
                <p className={`font-medium text-sm ${activeView === item.id ? 'text-primary' : ''}`}>
                  {t(item.label) || item.label}
                </p>
              </div>
            ))}
          </div>
        </aside>

        {/* Middle Panel: Active View */}
        <section className="flex-1 bg-background p-6 overflow-y-auto">
          {renderActiveView()}
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const [booting, setBooting] = useState(true);

  return (
    <ThemeProvider defaultTheme="dark" storageKey="darknight-theme">
      {booting ? (
        <BootupAnimation onComplete={() => setBooting(false)} />
      ) : (
        <Dashboard />
      )}
    </ThemeProvider>
  );
}
