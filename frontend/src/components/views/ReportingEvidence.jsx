import { useEffect, useState } from 'react';

import {
  FileText,
  RefreshCw,
  Users,
  Database,
  Calendar,
  ChevronRight,
  AlertCircle,
  ArrowLeft,
  Shield,
} from 'lucide-react';
import {
  listGlobalReports,
  getInvestigationReport,
  downloadInvestigationReportPdf,
} from '../../api/investigationReportsApi';

function formatDate(dateString) {
  if (!dateString) return 'N/A';

  try {
    return new Date(dateString).toLocaleString();
  } catch {
    return 'N/A';
  }
}

function getPriorityLabel(priority) {
  if (priority === 1) return 'CRITICAL';
  if (priority === 2) return 'HIGH';
  if (priority === 3) return 'MEDIUM';
  if (priority === 4) return 'LOW';
  return 'NORMAL';
}

function getPriorityClass(priority) {
  if (priority === 1) {
    return 'text-red-400 border-red-400/30 bg-red-400/5';
  }

  if (priority === 2) {
    return 'text-orange-400 border-orange-400/30 bg-orange-400/5';
  }

  if (priority === 3) {
    return 'text-yellow-400 border-yellow-400/30 bg-yellow-400/5';
  }

  return 'text-muted-foreground border-border bg-background/20';
}

function ReportCard({ report, onClick }) {
  const officers = report.assigned_officers || [];
  const [downloadingPdf, setDownloadingPdf] = useState(false);

async function handleDownloadPdf() {
  try {
    setDownloadingPdf(true);

    const blob = await downloadInvestigationReportPdf(
      report.investigation_id,
      report.report_id,
    );

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = `${report.report_id}.pdf`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Failed to download report PDF:', err);
  } finally {
    setDownloadingPdf(false);
  }
}

  return (
    <button
      type="button"
      onClick={() => onClick(report)}
      className="group w-full text-left bracket-border bg-background/20 backdrop-blur-sm p-6 transition-colors hover:bg-primary/5 cursor-pointer"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center border border-primary/20 bg-primary/5">
            <FileText className="h-5 w-5 text-primary" />
          </div>

          <div className="min-w-0">
            <p className="text-[10px] font-mono tracking-widest uppercase text-primary">
              {report.investigation_id}
            </p>

            <h3 className="mt-2 truncate text-lg font-bold tracking-wide text-foreground">
              {report.case_title || report.title}
            </h3>

            <p className="mt-1 text-xs font-mono tracking-wider uppercase text-muted-foreground">
              {report.title}
            </p>
          </div>
        </div>

        <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-muted-foreground transition-all group-hover:translate-x-1 group-hover:text-primary" />
      </div>

      <div className="mt-6 border-t border-border/50 pt-5">
        <p className="mb-2 text-[10px] font-mono tracking-widest uppercase text-primary">
          Executive Summary
        </p>

        <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">
          {report.summary || 'No executive summary available.'}
        </p>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-5 border-t border-border/50 pt-5">
        <div className="flex items-center gap-3">
          <Users className="h-4 w-4 text-primary" />

          <div>
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Investigators
            </p>

            <p className="mt-1 text-sm font-bold text-foreground">
              {officers.length}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Database className="h-4 w-4 text-primary" />

          <div>
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Evidence
            </p>

            <p className="mt-1 text-sm font-bold text-foreground">
              {report.evidence_count ?? 0}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Calendar className="h-4 w-4 text-primary" />

          <div className="min-w-0">
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Generated
            </p>

            <p className="mt-1 truncate text-xs font-medium text-foreground">
              {formatDate(report.created_at)}
            </p>
          </div>
        </div>

        <div>
          <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
            Priority
          </p>

          <span
            className={`mt-2 inline-flex border px-2 py-1 text-[10px] font-mono tracking-wider ${getPriorityClass(
              report.priority,
            )}`}
          >
            {getPriorityLabel(report.priority)}
          </span>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between border-t border-border/50 pt-5">
        <span className="border border-primary/30 bg-primary/5 px-2.5 py-1 text-[10px] font-mono tracking-wider text-primary">
          {report.status}
        </span>

        <span className="text-[9px] font-mono tracking-wider text-muted-foreground/50">
          {report.report_id}
        </span>
      </div>
    </button>
  );
}

function ReportDetail({ report, onBack }) {
  const officers = report.assigned_officers || [];

  return (
    <div className="mx-auto max-w-5xl animate-in fade-in slide-in-from-bottom-4 duration-500">
      <button
        type="button"
        onClick={onBack}
        className="mb-6 flex items-center gap-2 text-xs font-mono tracking-widest uppercase text-muted-foreground transition-colors hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Reports
      </button>

      <div className="bracket-border bg-background/20 backdrop-blur-sm p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center border border-primary/20 bg-primary/5">
              <Shield className="h-6 w-6 text-primary" />
            </div>

            <div>
              <p className="text-[10px] font-mono tracking-widest uppercase text-primary">
                Investigation
              </p>

              <h2 className="mt-2 text-2xl font-black tracking-wider text-foreground">
                {report.investigation_id}
              </h2>

              <p className="mt-1 text-sm text-muted-foreground">
                {report.case_title || 'Untitled Case'}
              </p>
            </div>
          </div>

          <span className="w-fit border border-primary/30 bg-primary/5 px-3 py-1 text-[10px] font-mono tracking-widest text-primary">
            {report.status}
          </span>
        </div>

        <div className="mt-7 grid grid-cols-2 gap-5 border-t border-border/50 pt-6 md:grid-cols-4">
          <div>
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Case Type
            </p>

            <p className="mt-2 text-sm font-medium text-foreground">
              {report.case_type || 'N/A'}
            </p>
          </div>

          <div>
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Case Status
            </p>

            <p className="mt-2 text-sm font-medium text-foreground">
              {report.case_status || report.status || 'N/A'}
            </p>
          </div>

          <div>
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Priority
            </p>

            <span
              className={`mt-2 inline-flex border px-2 py-1 text-[10px] font-mono tracking-wider ${getPriorityClass(
                report.priority,
              )}`}
            >
              {getPriorityLabel(report.priority)}
            </span>
          </div>

          <div>
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Unit
            </p>

            <p className="mt-2 text-sm font-medium text-foreground">
              {report.unit || 'N/A'}
            </p>
          </div>
        </div>

        {report.description && (
          <div className="mt-6 border-t border-border/50 pt-6">
            <p className="text-[10px] font-mono tracking-widest uppercase text-primary">
              Case Description
            </p>

            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              {report.description}
            </p>
          </div>
        )}

        <div className="mt-6 border-t border-border/50 pt-6">
          <p className="text-[10px] font-mono tracking-widest uppercase text-primary">
            Assigned Officers
          </p>

          {officers.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {officers.map((officer) => (
                <span
                  key={officer.id}
                  className="border border-border bg-background/30 px-3 py-1.5 text-xs font-mono text-muted-foreground"
                >
                  {officer.name || officer.email}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              No investigators assigned.
            </p>
          )}
        </div>

        {report.lead_investigator && (
          <div className="mt-5">
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground">
              Lead Investigator
            </p>

            <p className="mt-2 text-sm font-medium text-foreground">
              {report.lead_investigator.name ||
                report.lead_investigator.email}
            </p>
          </div>
        )}
      </div>

      <div className="mt-6 bracket-border bg-background/20 backdrop-blur-sm">
        <div className="border-b border-border/50 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-mono tracking-widest uppercase text-primary">
                Intelligence Report
              </p>

              <h1 className="mt-2 text-xl font-black tracking-wider text-foreground">
                {report.title}
              </h1>

              <p className="mt-2 font-mono text-[9px] tracking-wider text-muted-foreground/50">
                REPORT ID: {report.report_id}
              </p>
            </div>

            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              className="flex shrink-0 items-center gap-2 border border-primary/30 bg-primary/5 px-4 py-2 text-[10px] font-mono tracking-widest uppercase text-primary transition-colors hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FileText
                className={`h-4 w-4 ${
                  downloadingPdf ? 'animate-pulse' : ''
                }`}
              />

              {downloadingPdf ? 'Generating...' : 'Generate PDF'}
            </button>
          </div>
        </div>

        <div className="p-6">
          <div className="whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
            {report.content}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReportingEvidence() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [selectedReport, setSelectedReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  async function loadReports(showRefreshState = false) {
    try {
      setError('');

      if (showRefreshState) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const data = await listGlobalReports();

      setReports(data.reports || []);
    } catch (err) {
      console.error('Failed to load global reports:', err);
      setError(err.message || 'Failed to load reports.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadReports();
  }, []);
  async function handleReportClick(report) {
  try {
    setLoadingReport(true);
    setError('');

    const fullReport = await getInvestigationReport(
      report.investigation_id,
      report.report_id,
    );

    setSelectedReport({
      ...report,
      ...fullReport,
    });
  } catch (err) {
    console.error('Failed to load report:', err);
    setError(err.message || 'Failed to load report.');
  } finally {
    setLoadingReport(false);
  }
}

  if (loadingReport) {
  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="mx-auto flex min-h-[300px] max-w-5xl items-center justify-center bracket-border bg-background/20">
        <div className="flex items-center gap-3 text-sm font-mono tracking-widest uppercase text-primary">
          <RefreshCw className="h-5 w-5 animate-spin" />
          Loading report...
        </div>
      </div>
    </div>
  );
}

if (selectedReport) {
  return (
    <div className="h-full overflow-y-auto p-8">
      <ReportDetail
        report={selectedReport}
        onBack={() => setSelectedReport(null)}
      />
    </div>
  );
}

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="mx-auto max-w-6xl animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="mb-10 flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <FileText className="h-6 w-6 text-primary" />

              <h2 className="text-4xl font-black tracking-widest text-foreground">
                Reporting & Evidence
              </h2>
            </div>

            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              AI-grounded intelligence reports generated from reviewed
              findings and promoted evidence across active investigations.
            </p>
          </div>

          <button
            type="button"
            onClick={() => loadReports(true)}
            disabled={refreshing}
            className="flex items-center gap-2 border border-border bg-background/20 px-4 py-2 text-xs font-mono tracking-widest uppercase text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-primary disabled:opacity-50"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
            />
            Refresh
          </button>
        </div>

        {error && (
          <div className="mb-6 flex items-center gap-3 border border-red-400/30 bg-red-400/5 p-4 text-sm text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex min-h-[300px] items-center justify-center bracket-border bg-background/20">
            <div className="flex items-center gap-3 text-sm font-mono tracking-widest uppercase text-primary">
              <RefreshCw className="h-5 w-5 animate-spin" />
              Loading intelligence...
            </div>
          </div>
        ) : reports.length === 0 ? (
          <div className="bracket-border bg-background/20 p-12 text-center">
            <FileText className="mx-auto h-10 w-10 text-primary" />

            <h3 className="mt-5 text-xl font-black tracking-widest uppercase text-foreground">
              No Generated Reports
            </h3>

            <p className="mx-auto mt-3 max-w-lg text-sm leading-7 text-muted-foreground">
              Reports will appear here after relevant intelligence findings
              have been reviewed, promoted to evidence, and an AI-grounded
              investigation report has been generated.
            </p>
          </div>
        ) : (
          <>
            <div className="mb-5 flex items-end justify-between border-b border-border/50 pb-4">
              <div>
                <p className="text-xs font-mono tracking-widest uppercase text-primary">
                  Generated Reports
                </p>

                <p className="mt-1 text-xs font-mono text-muted-foreground">
                  {reports.length} REPORT{reports.length !== 1 ? 'S' : ''}{' '}
                  ACROSS ALL INVESTIGATIONS
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {reports.map((report) => (
                <ReportCard
                  key={report.report_id}
                  report={report}
                  onClick={handleReportClick}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}