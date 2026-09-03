import React, { useState } from 'react';
import { Shield, Users, LogOut, KeyRound, ShieldCheck, FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';
import UserManagementTable from '../admin/UserManagementTable';
import AuditLogViewer from '../audit/AuditLogViewer';
import TFAModal from '../auth/TFAModal';

export default function AccessControl() {
  const { t } = useTranslation();
  const { user, logout, checkAuth } = useAuth();
  const [showTFAModal, setShowTFAModal] = useState(false);
  const [showAdminTable, setShowAdminTable] = useState(false);
  const [showAuditLogs, setShowAuditLogs] = useState(false);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-5xl mx-auto h-full flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-2 font-mono uppercase text-glow text-primary">
          {t('Security & Access Control')}
        </h2>
        <p className="text-muted-foreground font-mono text-xs">
          {t('Manage roles, review audit logs, and ensure protection of sensitive investigative information.')}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Profile Card */}
        <div className="p-6 rounded-xl border border-border/60 bg-card shadow-lg flex flex-col items-center text-center font-mono">
          <div className="w-16 h-16 bg-primary/20 text-primary rounded-full flex items-center justify-center mb-3 border border-primary/40">
            <Shield className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-foreground">{user?.full_name || 'Investigator Session'}</h3>
          <p className="text-xs text-muted-foreground mb-1">{user?.email}</p>
          <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 bg-primary/10 border border-primary/30 rounded-full text-xs font-bold text-primary">
            Role: {user?.role || 'CONSTABLE'}
          </div>
          
          <div className="w-full border-t border-border/40 my-4 pt-4 text-xs text-left space-y-2 text-muted-foreground">
            <div>Badge Number: <span className="text-foreground font-semibold">{user?.badge_number || 'N/A'}</span></div>
            <div>Assigned Unit: <span className="text-foreground font-semibold">{user?.unit || 'Cyber Intelligence'}</span></div>
            <div>2FA Protection: <span className={user?.mfa_enabled ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
              {user?.mfa_enabled ? 'ENABLED (TOTP)' : 'DISABLED'}
            </span></div>
          </div>

          <div className="w-full flex gap-2 mt-auto">
            {!user?.mfa_enabled && (
              <Button onClick={() => setShowTFAModal(true)} variant="outline" size="sm" className="flex-1 gap-1 text-xs font-mono">
                <KeyRound className="w-4 h-4 text-amber-400" /> Enable 2FA
              </Button>
            )}
            <Button onClick={logout} variant="destructive" size="sm" className="flex-1 gap-1 text-xs font-mono">
              <LogOut className="w-4 h-4" /> {t('Secure Logout')}
            </Button>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="md:col-span-2 space-y-4 flex flex-col">
          <div 
            onClick={() => {
              setShowAdminTable(!showAdminTable);
              setShowAuditLogs(false);
            }}
            className="p-5 rounded-xl border border-border/60 bg-card hover:bg-muted/20 transition-colors flex items-center justify-between cursor-pointer"
          >
            <div className="flex items-center gap-4">
              <Users className="w-6 h-6 text-purple-400" />
              <div>
                <h4 className="font-semibold text-sm font-mono">{t('Officer Account Governance')}</h4>
                <p className="text-xs text-muted-foreground font-mono">{t('Approve pending registrations & assign role permissions.')}</p>
              </div>
            </div>
            <Button variant="outline" size="sm" className="font-mono text-xs">
              {showAdminTable ? 'Hide Table' : 'Manage'}
            </Button>
          </div>

          <div 
            onClick={() => {
              setShowAuditLogs(!showAuditLogs);
              setShowAdminTable(false);
            }}
            className="p-5 rounded-xl border border-border/60 bg-card hover:bg-muted/20 transition-colors flex items-center justify-between cursor-pointer"
          >
            <div className="flex items-center gap-4">
              <FileText className="w-6 h-6 text-amber-400" />
              <div>
                <h4 className="font-semibold text-sm font-mono">{t('Immutable Audit Logs')}</h4>
                <p className="text-xs text-muted-foreground font-mono">{t('Inspect activity trail & export security records (Re-auth required).')}</p>
              </div>
            </div>
            <Button variant="outline" size="sm" className="font-mono text-xs">
              {showAuditLogs ? 'Hide Logs' : 'View Audit Logs'}
            </Button>
          </div>
        </div>
      </div>

      {showAdminTable && (
        <div className="mt-4 animate-in fade-in slide-in-from-top-4">
          <UserManagementTable />
        </div>
      )}

      {showAuditLogs && (
        <div className="mt-4 animate-in fade-in slide-in-from-top-4">
          <AuditLogViewer />
        </div>
      )}

      {showTFAModal && (
        <TFAModal
          onClose={() => setShowTFAModal(false)}
          onComplete={() => {
            setShowTFAModal(false);
            checkAuth();
          }}
        />
      )}
    </div>
  );
}
