import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FileText, Download, ShieldCheck } from 'lucide-react';
import { Button } from '../ui/button';

export default function ReportingEvidence() {
  const { t } = useTranslation();
  const [reports, setReports] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/reports')
      .then(res => res.json())
      .then(data => setReports(data));
  }, []);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h2 className="text-2xl font-bold tracking-tight mb-2">{t('Reporting & Evidence Management')}</h2>
          <p className="text-muted-foreground">{t('Generate structured intelligence reports and manage digitally signed evidence logs.')}</p>
        </div>
        <Button className="bg-blue-600 hover:bg-blue-700 text-white gap-2">
          <FileText className="w-4 h-4" /> {t('Generate New Report')}
        </Button>
      </div>

      <div className="bg-card border rounded-xl overflow-hidden shadow-sm">
        <div className="grid grid-cols-5 gap-4 p-4 border-b bg-muted/30 font-semibold text-sm text-muted-foreground">
          <div className="col-span-2">{t('Report Title')}</div>
          <div>{t('Author')}</div>
          <div>{t('Date')}</div>
          <div className="text-right">{t('Actions')}</div>
        </div>
        
        <div className="divide-y divide-border/50">
          {reports.map(rep => (
            <div key={rep.id} className="grid grid-cols-5 gap-4 p-4 items-center hover:bg-muted/10 transition-colors">
              <div className="col-span-2 flex items-center gap-3">
                <FileText className="w-5 h-5 text-blue-500" />
                <div>
                  <p className="font-medium">{t(rep.title) || rep.title}</p>
                  <div className="flex items-center gap-1 text-xs mt-0.5">
                    {rep.status === 'Finalized' ? (
                      <span className="text-green-500 flex items-center gap-1"><ShieldCheck className="w-3 h-3"/> {t('Sealed')}</span>
                    ) : (
                      <span className="text-yellow-500">{t('Draft')}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="text-sm">{t(rep.author) || rep.author}</div>
              <div className="text-sm text-muted-foreground">{rep.date}</div>
              <div className="text-right">
                <Button variant="ghost" size="sm" className="gap-2">
                  <Download className="w-4 h-4" /> {t('PDF')}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
