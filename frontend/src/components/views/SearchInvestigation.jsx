import { useState, useEffect } from 'react';
import { Search, History, Filter } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';

export default function SearchInvestigation() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    
    setIsSearching(true);
    try {
      const res = await fetch(`http://localhost:8000/api/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data.results);
    } catch (err) {
      console.error(err);
    }
    setIsSearching(false);
  };

  useEffect(() => {
    handleSearch();
  }, []);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full flex flex-col">
      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight mb-2">{t('Search & Investigation Support')}</h2>
        <p className="text-muted-foreground">Perform advanced searches across aliases, wallet addresses, and keywords.</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 mb-8">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by BTC address, alias, or keyword..." 
            className="w-full pl-10 pr-4 py-3 rounded-lg border bg-card text-card-foreground shadow-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
          />
        </div>
        <Button type="button" variant="outline" className="h-[50px] px-4"><Filter className="w-5 h-5 mr-2"/> Filters</Button>
        <Button type="submit" className="h-[50px] px-8 bg-blue-600 hover:bg-blue-700 text-white font-medium" disabled={isSearching}>
          {isSearching ? 'Searching...' : 'Search'}
        </Button>
      </form>

      <div className="flex-1 flex flex-col">
        {results.length > 0 ? (
          <div className="space-y-3">
            <h3 className="font-semibold text-lg mb-3">Intelligence Results ({results.length})</h3>
            {results.map((res, i) => (
              <div key={i} className="p-4 rounded-xl border bg-card hover:bg-muted/30 transition-colors cursor-pointer flex justify-between items-center">
                <div className="flex flex-col gap-1">
                  <span className="font-mono font-medium text-blue-500">{res.identifier}</span>
                  <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">{res.type}</span>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Risk Score:</span>
                    <span className={`text-sm font-bold ${res.risk_score > 85 ? 'text-red-500' : 'text-yellow-500'}`}>{res.risk_score}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">Last seen: {res.last_seen}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
            <History className="w-12 h-12 mb-4 opacity-20" />
            <p>Enter a query to search intelligence records.</p>
            <p className="text-sm mt-1 opacity-70">Historical records are automatically maintained for audit purposes.</p>
          </div>
        )}
      </div>
    </div>
  );
}
