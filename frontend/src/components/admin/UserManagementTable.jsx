import React, { useState, useEffect } from 'react';
import { Users, CheckCircle, XCircle, ShieldAlert, UserCheck, RefreshCw, AlertTriangle } from 'lucide-react';
import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';

const ROLE_RANK = {
  "SUPER ADMIN / DGP": 0,
  "IGP": 1,
  "SP": 2,
  "INSPECTOR": 3,
  "INVESTIGATOR": 4,
  "CONSTABLE": 5
};

export default function UserManagementTable() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [statusFilter, setStatusFilter] = useState('PENDING');
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [selectedRoles, setSelectedRoles] = useState({});

  const fetchUsers = async () => {
    setLoading(true);
    setActionError('');
    try {
      const url = statusFilter ? `/api/admin/users?status=${statusFilter}` : '/api/admin/users';
      const res = await fetch(url);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to fetch users');
      }
      const data = await res.json();
      setUsers(data);
      
      // Initialize selected roles state
      const rolesMap = {};
      data.forEach(u => {
        rolesMap[u.id] = u.role || 'CONSTABLE';
      });
      setSelectedRoles(rolesMap);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [statusFilter]);

  const handleApproveReject = async (targetUserId, action) => {
    setActionError('');
    setActionSuccess('');
    try {
      const assignedRole = selectedRoles[targetUserId] || 'CONSTABLE';
      const res = await fetch('/api/admin/approve-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_user_id: targetUserId,
          action: action,
          assigned_role: assignedRole
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Action failed');
      
      setActionSuccess(data.message);
      fetchUsers();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleSuspend = async (targetUserId) => {
    setActionError('');
    setActionSuccess('');
    try {
      const res = await fetch('/api/admin/suspend-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_user_id: targetUserId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Suspension failed');
      
      setActionSuccess(data.message);
      fetchUsers();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const myRank = ROLE_RANK[currentUser?.role] ?? 99;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold tracking-tight flex items-center gap-2 font-mono">
            <Users className="w-5 h-5 text-primary" /> Officer Account Governance
          </h3>
          <p className="text-xs text-muted-foreground font-mono">
            Approve pending registrations, assign role permissions, or revoke user sessions.
          </p>
        </div>

        <div className="flex gap-2">
          {['PENDING', 'ACTIVE', 'SUSPENDED', 'REJECTED'].map((st) => (
            <Button
              key={st}
              variant={statusFilter === st ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(st)}
              className="font-mono text-xs"
            >
              {st}
            </Button>
          ))}
          <Button variant="ghost" size="sm" onClick={fetchUsers} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="p-3 bg-destructive/15 border border-destructive/40 text-destructive text-xs font-mono rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {actionSuccess && (
        <div className="p-3 bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 text-xs font-mono rounded-lg flex items-center gap-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-muted/40 border-b border-border/60 text-muted-foreground uppercase">
            <tr>
              <th className="p-3">Officer Details</th>
              <th className="p-3">Badge & Unit</th>
              <th className="p-3">Status</th>
              <th className="p-3">Assign Role (Hierarchy Enforced)</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {users.length === 0 ? (
              <tr>
                <td colSpan="5" className="p-6 text-center text-muted-foreground">
                  No accounts found with status: {statusFilter}
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-muted/20">
                  <td className="p-3">
                    <div className="font-semibold text-foreground">{u.full_name}</div>
                    <div className="text-muted-foreground text-[11px]">{u.email}</div>
                  </td>
                  <td className="p-3">
                    <div>{u.badge_number || 'N/A'}</div>
                    <div className="text-muted-foreground text-[11px]">{u.unit || 'General'}</div>
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      u.account_status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
                      u.account_status === 'PENDING' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
                      'bg-destructive/20 text-destructive border border-destructive/40'
                    }`}>
                      {u.account_status}
                    </span>
                  </td>
                  <td className="p-3">
                    <select
                      value={selectedRoles[u.id] || u.role}
                      onChange={(e) => setSelectedRoles({ ...selectedRoles, [u.id]: e.target.value })}
                      disabled={u.account_status !== 'PENDING'}
                      className="bg-background border border-border/60 rounded px-2 py-1 text-xs font-mono focus:border-primary disabled:opacity-50"
                    >
                      {Object.keys(ROLE_RANK).map((r) => {
                        const rRank = ROLE_RANK[r];
                        // Disable if role is equal or higher than current user's role (Rule 4 constraint)
                        const disabled = rRank <= myRank;
                        return (
                          <option key={r} value={r} disabled={disabled}>
                            {r} {disabled ? '(Restricted)' : ''}
                          </option>
                        );
                      })}
                    </select>
                  </td>
                  <td className="p-3 text-right space-x-2">
                    {u.account_status === 'PENDING' && (
                      <>
                        <Button
                          size="sm"
                          onClick={() => handleApproveReject(u.id, 'APPROVE')}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white h-7 text-xs px-2 gap-1 font-mono"
                        >
                          <UserCheck className="w-3 h-3" /> Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleApproveReject(u.id, 'REJECT')}
                          className="h-7 text-xs px-2 gap-1 font-mono"
                        >
                          <XCircle className="w-3 h-3" /> Reject
                        </Button>
                      </>
                    )}

                    {u.account_status === 'ACTIVE' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSuspend(u.id)}
                        disabled={ROLE_RANK[u.role] <= myRank}
                        className="border-destructive/50 text-destructive hover:bg-destructive/10 h-7 text-xs px-2 gap-1 font-mono"
                      >
                        <ShieldAlert className="w-3 h-3" /> Suspend
                      </Button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
