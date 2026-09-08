import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Activity, Wallet, ShoppingBag, MessageSquare, ShieldAlert } from 'lucide-react';
import { apiFetch } from '../../lib/apiClient';

export default function SuspectProfiles() {
  const { t } = useTranslation();
  const [suspects, setSuspects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [suspectDetail, setSuspectDetail] = useState({});

  useEffect(() => {
    apiFetch('/api/suspects?limit=100')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data && Array.isArray(data.suspects)) {
          setSuspects(data.suspects);
        }
      })
      .catch(err => console.error("Error fetching suspects:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleToggleExpand = (suspect) => {
    const profileKey = `${suspect.profile_type || 'suspect'}:${suspect.id}`;
    if (expandedId === profileKey) {
      setExpandedId(null);
      return;
    }

    setExpandedId(profileKey);
    if (!suspectDetail[profileKey]) {
      const detailPath = suspect.crawler_candidate
        ? `/api/crawler-candidates/${suspect.id}`
        : `/api/suspects/${suspect.id}`;
      fetch(detailPath)
        .then(res => res.ok ? res.json() : null)
        .then(detail => {
          if (detail) {
            setSuspectDetail(prev => ({ ...prev, [profileKey]: detail }));
          }
        })
        .catch(err => console.error(`Error fetching detail for profile ${profileKey}:`, err));
    }
  };

  return (
    <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-black tracking-widest mb-2 uppercase text-foreground">{t('Target Profiles')}</h2>
          <p className="text-muted-foreground font-mono tracking-wider uppercase text-xs">{t('Monitored threat actor entities, darknet vendors, and OFAC targets in SQLite database.')}</p>
        </div>
        <div className="text-right font-mono text-xs">
          <span className="text-primary font-bold">{suspects.length} {t('Entities Registered')}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-4">
        {loading ? (
          <div className="text-center text-muted-foreground py-10 animate-pulse font-mono tracking-widest uppercase text-sm">
            {t('Loading target profiles...')}
          </div>
        ) : suspects.length === 0 ? (
          <div className="text-center text-muted-foreground py-10 font-mono tracking-widest uppercase text-sm">
            {t('No target profiles found')}
          </div>
        ) : (
          suspects.map((suspect) => {
            const profileKey = `${suspect.profile_type || 'suspect'}:${suspect.id}`;
            const detail = suspectDetail[profileKey];

            return (
              <div key={profileKey} className="bracket-border bg-background/40 backdrop-blur-sm transition-all">
                <div
                  className="p-4 flex items-center justify-between cursor-pointer hover:bg-primary/5 transition-colors group"
                  onClick={() => handleToggleExpand(suspect)}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary border border-primary/30 font-bold">
                      👤
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <h3 className="font-bold text-lg text-foreground tracking-wide">{suspect.label}</h3>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${suspect.crawler_candidate ? 'bg-cyan-500/15 text-cyan-400' : suspect.data_origin?.includes('crawler_enriched') ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground'}`}>
                          {suspect.crawler_candidate ? 'Crawler profile' : suspect.data_origin?.includes('crawler_enriched') ? 'Crawler enriched' : 'Base dataset'}
                        </span>
                        {suspect.telegram_handle && (
                          <span className="text-xs bg-cyan-500/10 text-cyan-500 px-2 py-0.5 rounded font-mono">{suspect.telegram_handle}</span>
                        )}
                      </div>
                      <p className="text-xs font-mono text-muted-foreground uppercase tracking-widest mt-1">
                        {t('Risk Score')}: <span className={suspect.risk_score >= 80 ? 'text-red-500 font-bold' : 'text-primary font-bold'}>{suspect.risk_score} ({t(suspect.risk_level)})</span>
                        <span className="ml-3 text-muted-foreground/80">Wallets: {suspect.wallets_count} | Listings: {suspect.listings_count} | Messages: {suspect.telegram_messages_count}</span>
                      </p>
                    </div>
                  </div>
                  <div className="text-muted-foreground group-hover:text-primary transition-colors">
                    {expandedId === profileKey ? <ChevronDown /> : <ChevronRight />}
                  </div>
                </div>

                <AnimatePresence>
                  {expandedId === profileKey && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden border-t border-border/30"
                    >
                      <div className="p-6 grid grid-cols-2 gap-8 font-mono text-xs">
                        {/* Left side: Details & Aliases */}
                        <div className="space-y-4">
                          <h4 className="text-xs font-mono tracking-widest uppercase text-primary mb-3 flex items-center gap-2">
                            <ShieldAlert className="w-4 h-4" /> {t('Intelligence Metadata')}
                          </h4>
                          <div>
                            <span className="text-muted-foreground uppercase text-[10px] tracking-widest block mb-1">{t('Notes')}</span>
                            <p className="text-foreground bg-muted/20 p-2.5 rounded text-[11px] leading-relaxed">{suspect.notes}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground uppercase text-[10px] tracking-widest block mb-1">{t('Known Aliases')}</span>
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {suspect.aliases?.map((a, idx) => (
                                <span key={idx} className="bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded text-[10px]">
                                  {a}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="border-t border-border/20 pt-3 space-y-2">
                            <span className="text-emerald-400 uppercase text-[10px] tracking-widest block">Crawler Enrichment</span>
                            {detail ? (
                              detail.enrichment_source_count > 0 ? (
                                <div className="space-y-2 text-[11px]">
                                  <div><span className="text-muted-foreground">Phone:</span> {detail.phone_number || 'Not observed'}</div>
                                  <div><span className="text-muted-foreground">Last known location:</span> {detail.last_known_location || 'Not observed'}</div>
                                  <div><span className="text-muted-foreground">Platform mentions:</span> {detail.platform_mentions?.length ? detail.platform_mentions.join(', ') : 'None observed'}</div>
                                  <p className="text-foreground bg-muted/20 p-2 rounded leading-relaxed">{detail.enrichment_summary || 'No additional intelligence gathered yet'}</p>
                                  <div className="text-muted-foreground">Enriched from {detail.enrichment_source_count} crawler source{detail.enrichment_source_count === 1 ? '' : 's'}{detail.last_enriched_at ? `, last updated ${new Date(detail.last_enriched_at).toLocaleString()}` : ''}.</div>
                                </div>
                              ) : (
                                <p className="text-muted-foreground text-[11px]">No additional intelligence gathered yet</p>
                              )
                            ) : (
                              <p className="text-muted-foreground text-[11px] animate-pulse">Loading enrichment details...</p>
                            )}
                          </div>
                          <div className="flex justify-between text-[11px] text-muted-foreground pt-2 border-t border-border/20">
                            <span>{t('Record ID')}: #{suspect.id}</span>
                            <span>{t('Last Synced')}: {suspect.last_active}</span>
                          </div>
                        </div>

                        {/* Right side: Linked Intelligence Artifacts */}
                        <div className="space-y-4">
                          <h4 className="text-xs font-mono tracking-widest uppercase text-primary mb-3 flex items-center gap-2">
                            <Activity className="w-4 h-4" /> {t('Linked Domain Artifacts')}
                          </h4>

                          {!detail ? (
                            <div className="text-muted-foreground animate-pulse text-[11px] py-4">{t('Loading linked wallet and listing details...')}</div>
                          ) : (
                            <div className="space-y-4">
                              {/* Linked Wallets */}
                              {detail.wallets?.length > 0 && (
                                <div>
                                  <span className="text-yellow-500 uppercase text-[10px] tracking-widest flex items-center gap-1 mb-1.5 font-bold">
                                    <Wallet className="w-3.5 h-3.5" /> Linked Crypto Wallets ({detail.wallets.length})
                                  </span>
                                  <div className="space-y-1.5">
                                    {detail.wallets.map(w => (
                                      <div key={w.id} className="p-2 rounded bg-card border border-border/40 flex justify-between items-center text-[10px]">
                                        <span className="text-yellow-500 font-mono font-bold truncate max-w-[220px]">{w.address}</span>
                                        <span className={`px-1.5 py-0.5 rounded font-bold ${w.risk_level === 'SANCTIONED' ? 'bg-red-500/20 text-red-500' : 'bg-muted text-muted-foreground'}`}>{w.risk_level}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Linked Listings */}
                              {detail.listings?.length > 0 && (
                                <div>
                                  <span className="text-purple-400 uppercase text-[10px] tracking-widest flex items-center gap-1 mb-1.5 font-bold">
                                    <ShoppingBag className="w-3.5 h-3.5" /> Linked Darknet Listings ({detail.listings.length})
                                  </span>
                                  <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                                    {detail.listings.map(l => (
                                      <div key={l.id} className="p-2 rounded bg-card border border-border/40 text-[10px] space-y-0.5">
                                        <div className="font-bold text-foreground truncate">{l.title}</div>
                                        <div className="text-muted-foreground flex justify-between">
                                          <span>{l.drug_category}</span>
                                          <span className="text-primary font-bold">{l.price}</span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Linked Telegram Communications */}
                              {detail.telegram_messages?.length > 0 && (
                                <div>
                                  <span className="text-cyan-400 uppercase text-[10px] tracking-widest flex items-center gap-1 mb-1.5 font-bold">
                                    <MessageSquare className="w-3.5 h-3.5" /> Internet Activity (Telegram and other social media) Messages ({detail.telegram_messages.length})
                                  </span>
                                  <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                                    {detail.telegram_messages.slice(0, 3).map(m => (
                                      <div key={m.id} className="p-2 rounded bg-muted/20 border border-border/30 text-[10px] space-y-1">
                                        <p className="text-foreground line-clamp-2">{m.message_text}</p>
                                        <span className="text-muted-foreground block text-[9px]">{new Date(m.timestamp).toLocaleDateString()} | Channel: {m.channel_name}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {(!detail.wallets?.length && !detail.listings?.length && !detail.telegram_messages?.length) && (
                                <div className="text-muted-foreground text-[11px] py-2">{t('No direct child records linked.')}</div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

