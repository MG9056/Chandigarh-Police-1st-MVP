import { Shield, Users, LogOut, KeyRound } from 'lucide-react';
import { Button } from '../ui/button';

export default function AccessControl() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto h-full flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">Security & Access Control</h2>
        <p className="text-muted-foreground">Manage roles, review audit logs, and ensure protection of sensitive investigative information.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Profile Card */}
        <div className="p-6 rounded-xl border bg-card shadow-sm flex flex-col items-center text-center">
          <div className="w-20 h-20 bg-blue-500/20 text-blue-500 rounded-full flex items-center justify-center mb-4">
            <Shield className="w-10 h-10" />
          </div>
          <h3 className="text-xl font-bold">Investigator Session</h3>
          <p className="text-muted-foreground mb-1">Clearance Level: Top Secret (Tier 1)</p>
          <p className="text-sm text-green-500 font-mono mb-6">Connection: Secure (256-bit AES)</p>
          
          <Button variant="destructive" className="w-full gap-2 mt-auto">
            <LogOut className="w-4 h-4" /> Secure Logout
          </Button>
        </div>

        {/* Audit Settings */}
        <div className="space-y-4 flex flex-col">
          <div className="p-5 rounded-xl border bg-card hover:bg-muted/20 transition-colors flex items-center justify-between cursor-pointer">
            <div className="flex items-center gap-4">
              <Users className="w-6 h-6 text-purple-500" />
              <div>
                <h4 className="font-semibold">Role Management</h4>
                <p className="text-sm text-muted-foreground">Manage investigator access levels.</p>
              </div>
            </div>
            <Button variant="outline" size="sm">Configure</Button>
          </div>

          <div className="p-5 rounded-xl border bg-card hover:bg-muted/20 transition-colors flex items-center justify-between cursor-pointer">
            <div className="flex items-center gap-4">
              <KeyRound className="w-6 h-6 text-yellow-500" />
              <div>
                <h4 className="font-semibold">Audit Logs</h4>
                <p className="text-sm text-muted-foreground">Review system access and search history.</p>
              </div>
            </div>
            <Button variant="outline" size="sm">View Logs</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
