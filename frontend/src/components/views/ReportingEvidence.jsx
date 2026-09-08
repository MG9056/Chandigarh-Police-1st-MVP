import { useTranslation } from 'react-i18next';
import { ScrollText, FolderOpen, ArrowRight } from 'lucide-react';

/**
 * ReportingEvidence — Global Reports View
 *
 * Intelligence reports in DarKnight are scoped to individual investigations.
 * They are generated using AI grounded on reviewed findings and promoted evidence.
 *
 * To access reports: open an Investigation → click the "Reports" tab.
 */
export default function ReportingEvidence() {
  const { t } = useTranslation();

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full font-mono">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold tracking-tight mb-2 uppercase">
          {t('Reporting & Evidence Management')}
        </h2>
        <p className="text-muted-foreground text-xs">
          {t('Generate structured intelligence reports and manage digitally signed evidence logs.')}
        </p>
      </div>

      {/* Info panel */}
      <div className="p-8 bg-card/40 border border-border/50 rounded-xl text-center space-y-5">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
            <ScrollText className="w-8 h-8 text-primary" />
          </div>
        </div>

        <div className="space-y-2">
          <h3 className="text-base font-bold uppercase tracking-wider">
            {t('Reports Are Investigation-Scoped')}
          </h3>
          <p className="text-muted-foreground text-xs max-w-lg mx-auto leading-relaxed">
            Intelligence reports in DarKnight are AI-grounded documents tied to a specific
            investigation. They are generated from reviewed intelligence findings and promoted
            evidence records, ensuring full traceability.
          </p>
        </div>

        <div className="space-y-2 text-left max-w-sm mx-auto">
          <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider text-center">
            {t('How to generate a report')}
          </p>
          {[
            'Open an Investigation from the Investigations view',
            'Mark intelligence findings as RELEVANT in the Intelligence tab',
            'Promote relevant findings to evidence in the Findings tab',
            'Click the Reports tab → Generate Report',
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3 text-xs">
              <span className="w-5 h-5 rounded-full bg-primary/20 border border-primary/30 text-primary flex-shrink-0 flex items-center justify-center text-[10px] font-bold">
                {i + 1}
              </span>
              <span className="text-muted-foreground">{step}</span>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground pt-2">
          <FolderOpen className="w-3.5 h-3.5" />
          <span>{t('Navigate to')}</span>
          <span className="text-primary font-bold">Investigations</span>
          <ArrowRight className="w-3 h-3" />
          <span className="text-primary font-bold">{t('Select an Investigation')}</span>
          <ArrowRight className="w-3 h-3" />
          <span className="text-primary font-bold">{t('Reports tab')}</span>
        </div>
      </div>
    </div>
  );
}

