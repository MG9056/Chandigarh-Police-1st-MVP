import { useTranslation } from 'react-i18next';
import { Activity, ShieldAlert, Network } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTheme } from '../theme-provider';
import { LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const listingsData = [
  { time: 'Mon', listings: 120 },
  { time: 'Tue', listings: 180 },
  { time: 'Wed', listings: 250 },
  { time: 'Thu', listings: 210 },
  { time: 'Fri', listings: 340 },
  { time: 'Sat', listings: 400 },
  { time: 'Sun', listings: 380 },
];

const drugData = [
  { name: 'Opiates', value: 45 },
  { name: 'Stimulants', value: 25 },
  { name: 'Psychedelics', value: 20 },
  { name: 'Prescription', value: 10 },
];
const COLORS = ['hsl(84, 100%, 50%)', 'hsl(84, 100%, 30%)', 'hsl(84, 100%, 20%)', 'hsl(84, 100%, 10%)'];

export default function DashboardOverview({ setActiveView }) {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/dashboard/summary')
      .then(res => res.json())
      .then(data => setSummary(data))
      .catch(err => console.error("Error fetching summary:", err));
  }, []);

  if (!summary) return <div className="p-8 text-center text-muted-foreground animate-pulse">{t('Loading dashboard intelligence...')}</div>;

  return (
    <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      <h2 className="text-4xl font-black mb-10 tracking-widest text-foreground">{t('Welcome to DarKnight')}</h2>
      
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
      
      <div className="grid grid-cols-3 gap-6 mb-10">
        <div className="col-span-2 bracket-border bg-background/20 backdrop-blur-sm p-6 relative flex flex-col justify-center min-h-[300px]">
          <h3 className="text-sm font-mono tracking-widest uppercase text-primary mb-4 absolute top-6 left-6">{t('Listings Over Time')}</h3>
          <div className="w-full h-full pt-10">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={listingsData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: 'hsl(var(--background))', border: '1px solid hsl(var(--border))' }}
                  itemStyle={{ color: 'hsl(var(--primary))' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="listings" 
                  stroke="hsl(var(--primary))" 
                  strokeWidth={3}
                  dot={{ fill: 'hsl(var(--background))', stroke: 'hsl(var(--primary))', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, fill: 'hsl(var(--primary))' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-1 bracket-border bg-background/20 backdrop-blur-sm p-6 relative flex flex-col justify-center items-center">
           <h3 className="text-sm font-mono tracking-widest uppercase text-primary mb-6 absolute top-6 left-6 w-full text-left">{t('Drug Distribution')}</h3>
           
           <div className="w-full h-48 mt-8 relative">
             <ResponsiveContainer width="100%" height="100%">
               <PieChart>
                 <Pie
                   data={drugData}
                   innerRadius={60}
                   outerRadius={80}
                   paddingAngle={5}
                   dataKey="value"
                   stroke="none"
                 >
                   {drugData.map((entry, index) => (
                     <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                   ))}
                 </Pie>
                 <RechartsTooltip 
                   contentStyle={{ backgroundColor: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: '4px' }}
                   itemStyle={{ color: 'hsl(var(--foreground))' }}
                 />
               </PieChart>
             </ResponsiveContainer>
           </div>
           
           <div className="w-full mt-4 flex flex-col gap-2 text-xs font-mono tracking-wider uppercase">
             {drugData.map((entry, index) => (
               <div key={entry.name} className="flex justify-between items-center">
                 <div className="flex items-center gap-2">
                   <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></div>
                   <span className="text-muted-foreground">{t(entry.name)}</span>
                 </div>
                 <span className="text-foreground font-bold">{entry.value}%</span>
               </div>
             ))}
           </div>
        </div>
      </div>
      
      <div className="p-8 bracket-border bg-transparent relative">
        <h3 className="text-sm font-mono tracking-widest uppercase text-primary mb-4">{t('Details')}</h3>
        <p className="text-muted-foreground leading-relaxed text-lg font-light max-w-2xl">
          {t('Select an item from the Navigation panel to view detailed metrics, suspect relationships, or actionable intelligence here. The dashboard automatically aggregates signals across multiple encrypted channels.')}
        </p>
        <p className="text-xs font-mono tracking-wider text-muted-foreground mt-8 text-right opacity-50 uppercase">
          {t('Last Synced')}: {new Date(summary.last_update).toLocaleString()}
        </p>
      </div>
    </div>
  );
}
