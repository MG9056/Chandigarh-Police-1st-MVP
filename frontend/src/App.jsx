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
      case 'dashboard': return <DashboardOverview setActiveView={setActiveView} />;
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
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans relative z-0">
      {/* Flammini Style Background Effects */}
      <div className="absolute inset-0 pointer-events-none z-[-1] overflow-hidden">
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-primary/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-primary/10 rounded-full blur-[150px]" />
      </div>
      <div className="absolute inset-0 bg-noise z-[-1]" />

      <div className="flex flex-col flex-1 z-10 relative">
        {/* Header / Top Nav */}
        <header className="h-16 border-b border-border/50 bg-background/50 backdrop-blur-md flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <div className="relative w-8 h-8 flex items-center justify-center bracket-border">
              <div className="w-3 h-3 bg-primary rotate-45 text-glow" />
            </div>
            <h1 className="text-xl font-bold tracking-[0.2em] uppercase text-primary text-glow">DarKnight</h1>
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
          <aside className="w-[280px] border-r border-border/50 bg-background/30 backdrop-blur-sm p-6 overflow-y-auto flex-shrink-0">
            <div className="mb-8">
              <span className="text-xs font-mono tracking-widest text-muted-foreground uppercase border-b border-border/50 pb-2 block w-full">Navigation</span>
            </div>
            <div className="space-y-4">
              {navItems.map(item => (
                <div 
                  key={item.id}
                  onClick={() => setActiveView(item.id)}
                  className={`flex items-center gap-4 group cursor-pointer transition-colors ${
                    activeView === item.id 
                    ? 'text-primary' 
                    : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <div className={`w-2 h-2 rotate-45 flex-shrink-0 transition-all ${
                    activeView === item.id 
                    ? 'bg-primary shadow-[0_0_8px_hsl(var(--primary))]' 
                    : 'border border-muted-foreground group-hover:border-foreground'
                  }`} />
                  <p className="font-mono text-xs tracking-[0.15em] uppercase">
                    {t(item.label) || item.label}
                  </p>
                </div>
              ))}
            </div>
          </aside>

          {/* Middle Panel: Active View */}
          <section className="flex-1 bg-transparent p-8 overflow-y-auto">
            {renderActiveView()}
          </section>
        </main>
      </div>
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
