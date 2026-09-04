import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Activity } from 'lucide-react';
import { apiFetch } from '../../lib/apiClient';

const mockTransactions = [
  { id: 1, type: 'Receive', amount: '2.5 BTC', date: '2023-10-28', node: 'Mixer Node Alpha' },
  { id: 2, type: 'Send', amount: '0.8 BTC', date: '2023-10-29', node: 'Wallet 0x4B...' },
  { id: 3, type: 'Convert', amount: '1.7 BTC -> XMR', date: '2023-10-30', node: 'Exchange Delta' },
  { id: 4, type: 'Send', amount: '250 XMR', date: '2023-10-31', node: 'Market Escrow' }
];

export default function SuspectProfiles() {
  const { t } = useTranslation();
  const [suspects, setSuspects] = useState([]);
  const [loading, setLoading] = useState(true);

  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
  apiFetch('/api/network/data')
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (data && Array.isArray(data.nodes)) {
        const suspectNodes = data.nodes.filter(n => n.group === 'suspect');
        setSuspects(suspectNodes);
      }
    })
    .catch(err => console.error("Error fetching suspects:", err))
    .finally(() => setLoading(false));
}, []);

  return (
    <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-black tracking-widest mb-4 uppercase text-foreground">{t('Target Profiles')}</h2>
          <p className="text-muted-foreground font-mono tracking-wider uppercase text-xs">{t('Monitored individuals and marketplace vendors.')}</p>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto space-y-4 pr-4">
        {loading ? (
          <div className="text-center text-muted-foreground py-10 animate-pulse font-mono tracking-widest uppercase text-sm">
            {t('Loading profiles...')}
          </div>
        ) : suspects.length === 0 ? (
          <div className="text-center text-muted-foreground py-10 font-mono tracking-widest uppercase text-sm">
            {t('No target profiles found')}
          </div>
        ) : (
          suspects.map((suspect) => (
            <div key={suspect.id} className="bracket-border bg-background/40 backdrop-blur-sm transition-all">
              <div 
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-primary/5 transition-colors group"
                onClick={() => setExpandedId(expandedId === suspect.id ? null : suspect.id)}
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary border border-primary/30">
                    👤
                  </div>
                  <div>
                    <h3 className="font-bold text-lg text-foreground tracking-wide">{suspect.label}</h3>
                    <p className="text-xs font-mono text-muted-foreground uppercase tracking-widest mt-1">
                      {t('Risk')}: <span className={suspect.risk_level === 'Critical' ? 'text-red-500' : 'text-primary'}>{t(suspect.risk_level)}</span>
                    </p>
                  </div>
                </div>
                <div className="text-muted-foreground group-hover:text-primary transition-colors">
                  {expandedId === suspect.id ? <ChevronDown /> : <ChevronRight />}
                </div>
              </div>

              <AnimatePresence>
                {expandedId === suspect.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden border-t border-border/30"
                  >
                    <div className="p-6 grid grid-cols-2 gap-8">
                      {/* Left side: Details */}
                      <div>
                        <h4 className="text-xs font-mono tracking-widest uppercase text-primary mb-4">{t('Profile Details')}</h4>
                        <div className="space-y-4 text-sm">
                          <div>
                            <span className="text-muted-foreground uppercase text-[10px] tracking-widest block mb-1">{t('Notes')}</span>
                            <p className="text-foreground">{t(suspect.notes) || suspect.notes}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground uppercase text-[10px] tracking-widest block mb-1">{t('Last Active')}</span>
                            <p className="font-mono text-foreground">{suspect.last_active}</p>
                          </div>
                        </div>
                      </div>

                      {/* Right side: Transaction Timeline */}
                      <div>
                        <h4 className="text-xs font-mono tracking-widest uppercase text-primary mb-4 flex items-center gap-2">
                          <Activity className="w-4 h-4" /> {t('Transaction History')}
                        </h4>
                        <div className="relative border-l border-border/50 ml-3 space-y-6">
                          {mockTransactions.map((tx, idx) => (
                            <motion.div
                              key={tx.id}
                              initial={{ x: -20, opacity: 0 }}
                              animate={{ x: 0, opacity: 1 }}
                              transition={{ delay: idx * 0.2 }}
                              className="relative pl-6"
                            >
                              <div className="absolute w-2 h-2 bg-primary rounded-full left-[-4.5px] top-1.5 shadow-[0_0_8px_hsl(var(--primary))]"></div>
                              <div className="text-[10px] font-mono text-muted-foreground mb-1">{tx.date}</div>
                              <div className="flex items-baseline justify-between">
                                <span className={`font-bold ${tx.type === 'Receive' ? 'text-green-500' : tx.type === 'Send' ? 'text-red-500' : 'text-blue-500'}`}>
                                  {t(tx.type)}: {tx.amount}
                                </span>
                              </div>
                              <div className="text-xs text-muted-foreground mt-1">{t('Node')}: {tx.node}</div>
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
