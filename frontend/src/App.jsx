import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ThemeProvider, useTheme } from './components/theme-provider';
import BootupAnimation from './components/BootupAnimation';
import { Button } from './components/ui/button';
import { LogOut, User, Shield } from 'lucide-react';
import { useAuth } from './context/AuthContext';

import LoginPage from './components/auth/LoginPage';
import RegisterPage from './components/auth/RegisterPage';
import ReAuthModal from './components/auth/ReAuthModal';

import DashboardOverview from './components/views/DashboardOverview';
import NetworkGraph from './components/views/NetworkGraph';
import AlertsFeed from './components/views/AlertsFeed';
import SearchInvestigation from './components/views/SearchInvestigation';
import DataCollectionStatus from './components/views/DataCollectionStatus';
import ReportingEvidence from './components/views/ReportingEvidence';
import AccessControl from './components/views/AccessControl';
import TrafficHotspots from './components/views/TrafficHotspots';
import SuspectProfiles from './components/views/SuspectProfiles';

function Dashboard() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
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
      case 'hotspots': return <TrafficHotspots />;
      case 'profiles': return <SuspectProfiles />;
      default: return <DashboardOverview />;
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'hotspots', label: 'Traffic Hotspots' },
    { id: 'profiles', label: 'Target Profiles' },
    { id: 'data', label: 'Data Collection Status' },
    { id: 'alerts', label: 'Alerts & Suspicious Activity' },
    { id: 'network', label: 'Network Visualization' },
    { id: 'search', label: 'Search & Investigation' },
    { id: 'reports', label: 'Reports & Evidence' },
    { id: 'security', label: 'Security & Access Control' },
  ];

  return (
    <div className="h-screen bg-background text-foreground flex flex-col font-sans relative z-0 overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 pointer-events-none z-[-1] overflow-hidden">
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-primary/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-primary/10 rounded-full blur-[150px]" />
      </div>
      <div className="absolute inset-0 bg-noise z-[-1]" />

      <div className="flex flex-col w-full h-full z-10 relative overflow-hidden">
        {/* Header / Top Nav */}
        <header className="h-16 border-b border-border/50 bg-background/50 backdrop-blur-md flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <div className="relative w-8 h-8 flex items-center justify-center bracket-border">
              <div className="w-3 h-3 bg-primary rotate-45 text-glow" />
            </div>
            <h1 className="text-xl font-bold tracking-[0.2em] text-primary text-glow font-mono uppercase">DarKnight</h1>
          </div>

          <div className="flex items-center gap-4">
            {/* Authenticated Officer Badge */}
            {user && (
              <div className="flex items-center gap-3 px-3 py-1 bg-card/60 border border-border/50 rounded-lg text-xs font-mono">
                <div className="flex flex-col text-right">
                  <span className="font-bold text-foreground">{user.full_name}</span>
                  <span className="text-[10px] text-primary">{user.role}</span>
                </div>
                <Button variant="ghost" size="icon" onClick={logout} title="Secure Logout" className="h-7 w-7 text-muted-foreground hover:text-destructive">
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            )}

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
      <ReAuthModal />
    </div>
  );
}

export default function App() {
  const [booting, setBooting] = useState(true);
  const [showRegister, setShowRegister] = useState(false);
  const { isAuthenticated, isLoading } = useAuth();

  if (booting) {
    return (
      <ThemeProvider defaultTheme="dark" storageKey="darknight-theme">
        <BootupAnimation onComplete={() => setBooting(false)} />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider defaultTheme="dark" storageKey="darknight-theme">
      {isLoading ? (
        <div className="h-screen w-full flex items-center justify-center bg-background text-primary font-mono text-sm">
          Loading Security Credentials...
        </div>
      ) : !isAuthenticated ? (
        showRegister ? (
          <RegisterPage onSwitchToLogin={() => setShowRegister(false)} />
        ) : (
          <LoginPage onSwitchToRegister={() => setShowRegister(true)} />
        )
      ) : (
        <Dashboard />
      )}
    </ThemeProvider>
  );
}
