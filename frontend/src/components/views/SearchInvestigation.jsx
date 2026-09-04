import { useState, useEffect } from 'react';
import { Search, History, Filter, User, Wallet, ShoppingBag, MessageSquare, Tag } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';

export default function SearchInvestigation() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [searchResults, setSearchResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    
    setIsSearching(true);
    try {
      const url = `/api/search/universal?q=${encodeURIComponent(query)}&category=${categoryFilter}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
      }
    } catch (err) {
      console.error("Search error:", err);
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    handleSearch();
  }, [categoryFilter]);

  const totalResults = searchResults?.total_results ?? 0;
  const suspects = searchResults?.suspects ?? [];
  const wallets = searchResults?.wallets ?? [];
  const listings = searchResults?.listings ?? [];
  const telegramMsgs = searchResults?.telegram_messages ?? [];

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full flex flex-col font-mono">
      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight mb-2 uppercase">{t('Universal Intelligence Search')}</h2>
        <p className="text-muted-foreground text-xs">{t('Perform real-time substring and fuzzy searches across suspect profiles, crypto wallets, darknet listings, and Telegram communications.')}</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('Search by BTC address, vendor alias, handle, drug category, or keyword (e.g. Alpha, SUEX, bc1, opioids)...')} 
            className="w-full pl-10 pr-4 py-3 rounded-lg border bg-card text-card-foreground shadow-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-xs font-mono"
          />
        </div>
        <Button type="submit" className="h-[50px] px-8 bg-blue-600 hover:bg-blue-700 text-white font-mono text-xs" disabled={isSearching}>
          {isSearching ? t('Searching...') : t('Search')}
        </Button>
      </form>

      {/* Category Filter Badges */}
      <div className="flex gap-2 mb-6 text-xs overflow-x-auto pb-1">
        {['all', 'suspects', 'wallets', 'listings', 'telegram'].map(cat => (
          <button
            key={cat}
            type="button"
            onClick={() => setCategoryFilter(cat)}
            className={`px-3 py-1.5 rounded-full uppercase tracking-wider transition-colors flex items-center gap-1.5 ${
              categoryFilter === cat 
                ? 'bg-primary text-primary-foreground font-bold' 
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            {cat === 'suspects' && <User className="w-3.5 h-3.5" />}
            {cat === 'wallets' && <Wallet className="w-3.5 h-3.5" />}
            {cat === 'listings' && <ShoppingBag className="w-3.5 h-3.5" />}
            {cat === 'telegram' && <MessageSquare className="w-3.5 h-3.5" />}
            {t(cat)}
          </button>
        ))}
      </div>

      <div className="flex-1 flex flex-col space-y-6 overflow-y-auto pr-2">
        {isSearching ? (
          <div className="text-center text-muted-foreground py-10 animate-pulse text-xs uppercase tracking-widest">
            {t('Scanning database intelligence records...')}
          </div>
        ) : totalResults > 0 ? (
          <>
            <div className="text-xs text-muted-foreground uppercase tracking-widest mb-2 font-bold">
              {t('Total Results Found')}: <span className="text-primary">{totalResults}</span>
            </div>

            {/* Suspects Section */}
            {suspects.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-semibold text-xs uppercase tracking-wider text-primary flex items-center gap-2">
                  <User className="w-4 h-4" /> {t('Suspect Profiles')} ({suspects.length})
                </h3>
                {suspects.map(s => (
                  <div key={`suspect-${s.id}`} className="p-4 rounded-xl border bg-card hover:bg-muted/20 transition-colors flex justify-between items-start text-xs">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-foreground">{s.primary_alias}</span>
                        {s.telegram_handle && <span className="text-[10px] bg-cyan-500/10 text-cyan-500 px-2 py-0.5 rounded-full font-mono">{s.telegram_handle}</span>}
                      </div>
                      <p className="text-[11px] text-muted-foreground">{s.notes}</p>
                      <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded font-mono block w-fit">{s.match_reason}</span>
                    </div>
                    <div className="text-right space-y-1">
                      <span className={`text-xs font-bold px-2 py-1 rounded ${s.risk_score >= 80 ? 'bg-red-500/20 text-red-500' : 'bg-yellow-500/20 text-yellow-500'}`}>
                        Risk: {s.risk_score} ({s.risk_level})
                      </span>
                      <p className="text-[10px] text-muted-foreground mt-1">Wallets: {s.wallets_count} | Listings: {s.listings_count}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Wallets Section */}
            {wallets.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-semibold text-xs uppercase tracking-wider text-yellow-500 flex items-center gap-2">
                  <Wallet className="w-4 h-4" /> {t('Crypto Wallets')} ({wallets.length})
                </h3>
                {wallets.map(w => (
                  <div key={`wallet-${w.id}`} className="p-4 rounded-xl border bg-card hover:bg-muted/20 transition-colors flex justify-between items-center text-xs">
                    <div>
                      <span className="font-bold text-xs font-mono text-yellow-500 block">{w.address}</span>
                      <span className="text-[11px] text-muted-foreground">Currency: {w.currency} | Associated Entity: {w.associated_suspect_alias || 'Unlinked'}</span>
                    </div>
                    <div className="text-right">
                      <span className={`px-2 py-1 rounded text-[11px] font-bold ${w.risk_level === 'SANCTIONED' ? 'bg-red-500/20 text-red-500' : w.risk_level === 'ILLICIT' ? 'bg-orange-500/20 text-orange-500' : 'bg-muted text-muted-foreground'}`}>
                        {w.risk_level}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Listings Section */}
            {listings.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-semibold text-xs uppercase tracking-wider text-purple-400 flex items-center gap-2">
                  <ShoppingBag className="w-4 h-4" /> {t('Darknet Marketplace Listings')} ({listings.length})
                </h3>
                {listings.map(l => (
                  <div key={`listing-${l.id}`} className="p-4 rounded-xl border bg-card hover:bg-muted/20 transition-colors flex justify-between items-start text-xs">
                    <div className="space-y-1">
                      <p className="font-bold text-sm text-foreground">{l.title}</p>
                      <p className="text-[11px] text-muted-foreground">Vendor: <span className="text-primary font-bold">{l.vendor_alias}</span> | Platform: {l.platform} | Shipping: {l.location}</p>
                      <span className="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded inline-block">{l.match_reason}</span>
                    </div>
                    <div className="text-right space-y-1">
                      <span className="bg-primary/20 text-primary font-bold px-2 py-1 rounded text-xs">{l.price}</span>
                      <p className="text-[10px] text-muted-foreground mt-1">{l.drug_category}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Telegram Messages Section */}
            {telegramMsgs.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-semibold text-xs uppercase tracking-wider text-cyan-400 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" /> {t('Telegram Communications')} ({telegramMsgs.length})
                </h3>
                {telegramMsgs.map(m => (
                  <div key={`telegram-${m.id}`} className="p-4 rounded-xl border bg-card hover:bg-muted/20 transition-colors text-xs space-y-2">
                    <div className="flex justify-between items-center text-muted-foreground text-[11px]">
                      <span className="text-cyan-400 font-bold">{m.channel_name}</span>
                      <span>Sender: <strong className="text-foreground">{m.sender_handle}</strong></span>
                      <span>{new Date(m.timestamp).toLocaleDateString()}</span>
                    </div>
                    <p className="text-foreground leading-relaxed bg-muted/30 p-2.5 rounded font-mono text-[11px]">{m.message_text}</p>
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-muted-foreground">Match: {m.match_reason}</span>
                      {m.detected_wallets?.length > 0 && (
                        <span className="text-yellow-500">Wallet Mentioned: {m.detected_wallets[0]}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl p-8">
            <History className="w-12 h-12 mb-4 opacity-20" />
            <p className="text-sm">{t('Enter a query to search intelligence database records.')}</p>
            <p className="text-xs mt-1 opacity-70">{t('Searches across 78 suspects, 924 wallets, 650 market listings, and 175 Telegram messages.')}</p>
          </div>
        )}
      </div>
    </div>
  );
}

