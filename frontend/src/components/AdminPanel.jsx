import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../utils/api";

function fmtBytes(b) {
  if (b == null) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
      <p className="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
      {sub && <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function RoleBadge({ role }) {
  return (
    <span className={[
      "inline-block px-2 py-0.5 rounded text-[11px] font-semibold",
      role === "admin"
        ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300"
        : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400",
    ].join(" ")}>
      {role}
    </span>
  );
}

const fieldCls = "block w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400";
const labelCls = "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1";

const EMPTY_FORM = { username: "", email: "", password: "", role: "user" };

export default function AdminPanel() {
  const [users,   setUsers]   = useState([]);
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [err,     setErr]     = useState(null);

  const [showCreate, setShowCreate] = useState(false);
  const [form,       setForm]       = useState(EMPTY_FORM);
  const [creating,   setCreating]   = useState(false);
  const [createErr,  setCreateErr]  = useState(null);

  const [actionErr, setActionErr] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const [uRes, sRes] = await Promise.all([
        apiFetch("/api/admin/users"),
        apiFetch("/api/admin/stats"),
      ]);
      if (!uRes.ok || !sRes.ok) throw new Error("Failed to load admin data");
      setUsers(await uRes.json());
      setStats(await sRes.json());
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function setF(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  async function handleCreate(e) {
    e.preventDefault();
    setCreating(true); setCreateErr(null);
    try {
      const res = await apiFetch("/api/admin/users", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      setForm(EMPTY_FORM);
      setShowCreate(false);
      await load();
    } catch (e) {
      setCreateErr(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(user) {
    setActionErr(null);
    const res = await apiFetch(`/api/admin/users/${user.id}`, {
      method:  "PUT",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ is_active: !user.is_active }),
    });
    if (!res.ok) { setActionErr("Could not update user"); return; }
    setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
  }

  async function toggleRole(user) {
    setActionErr(null);
    const newRole = user.role === "admin" ? "user" : "admin";
    const res = await apiFetch(`/api/admin/users/${user.id}`, {
      method:  "PUT",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ role: newRole }),
    });
    if (!res.ok) { setActionErr("Could not update role"); return; }
    setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, role: newRole } : u));
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400 dark:text-gray-500">
        <div className="flex items-center gap-2 text-sm">
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading…
        </div>
      </div>
    );
  }

  if (err) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-sm text-red-600 dark:text-red-400">{err}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin">
      <div className="p-5 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Admin Panel</h2>
          <button
            onClick={load}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 rounded-md px-3 py-1.5 transition-colors"
          >
            ↻ Refresh
          </button>
        </div>

        {/* ── Stats ── */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard label="Users"       value={stats.total_users}       sub={`${stats.active_users} active`} />
            <StatCard label="Transcripts" value={stats.total_transcripts} />
            <StatCard label="DB size"     value={fmtBytes(stats.db_size_bytes)} />
            <StatCard label="ChromaDB"    value={fmtBytes(stats.chroma_size_bytes)} />
            <StatCard label="Transcripts dir" value={fmtBytes(stats.transcripts_dir_size_bytes)} />
            <StatCard label="Inactive"    value={stats.total_users - stats.active_users} />
          </div>
        )}

        {/* ── Users ── */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/80">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Users</h3>
            <button
              onClick={() => { setShowCreate((s) => !s); setCreateErr(null); setForm(EMPTY_FORM); }}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-md px-3 py-1.5 font-medium transition-colors"
            >
              {showCreate ? "Cancel" : "+ New user"}
            </button>
          </div>

          {/* Create form */}
          {showCreate && (
            <form onSubmit={handleCreate} className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 bg-blue-50/30 dark:bg-blue-900/10">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className={labelCls}>Username *</label>
                  <input className={fieldCls} required value={form.username} onChange={(e) => setF("username", e.target.value)} placeholder="alice" />
                </div>
                <div>
                  <label className={labelCls}>Email</label>
                  <input className={fieldCls} type="email" value={form.email} onChange={(e) => setF("email", e.target.value)} placeholder="alice@example.com" />
                </div>
                <div>
                  <label className={labelCls}>Password *</label>
                  <input className={fieldCls} type="password" required value={form.password} onChange={(e) => setF("password", e.target.value)} autoComplete="new-password" />
                </div>
                <div>
                  <label className={labelCls}>Role</label>
                  <select className={fieldCls} value={form.role} onChange={(e) => setF("role", e.target.value)}>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
              </div>
              {createErr && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{createErr}</p>}
              <div className="mt-3 flex gap-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-md px-4 py-1.5 font-medium transition-colors inline-flex items-center gap-1.5"
                >
                  {creating && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  {creating ? "Creating…" : "Create user"}
                </button>
              </div>
            </form>
          )}

          {actionErr && (
            <div className="px-5 py-2 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border-b border-red-100 dark:border-red-800">
              {actionErr}
            </div>
          )}

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-400 dark:text-gray-500 uppercase tracking-wide border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left px-5 py-2.5 font-medium">User</th>
                  <th className="text-left px-4 py-2.5 font-medium">Email</th>
                  <th className="text-left px-4 py-2.5 font-medium">Role</th>
                  <th className="text-center px-4 py-2.5 font-medium">Active</th>
                  <th className="text-center px-4 py-2.5 font-medium">Transcripts</th>
                  <th className="text-left px-4 py-2.5 font-medium">Created</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-700/50">
                {users.map((u) => (
                  <tr key={u.id} className={[
                    "transition-colors",
                    u.is_active ? "hover:bg-gray-50 dark:hover:bg-gray-700/30" : "opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700/30",
                  ].join(" ")}>
                    <td className="px-5 py-3 font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{u.username}</td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">{u.email || "—"}</td>
                    <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                    <td className="px-4 py-3 text-center">
                      <span className={u.is_active ? "text-emerald-500" : "text-gray-300 dark:text-gray-600"}>
                        {u.is_active ? "●" : "○"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-400">{u.transcript_count}</td>
                    <td className="px-4 py-3 text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 justify-end">
                        <button
                          onClick={() => toggleRole(u)}
                          title={u.role === "admin" ? "Demote to user" : "Promote to admin"}
                          className="text-[11px] px-2 py-1 rounded border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        >
                          {u.role === "admin" ? "Demote" : "Promote"}
                        </button>
                        <button
                          onClick={() => toggleActive(u)}
                          title={u.is_active ? "Deactivate" : "Activate"}
                          className={[
                            "text-[11px] px-2 py-1 rounded border transition-colors",
                            u.is_active
                              ? "border-red-200 dark:border-red-800 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                              : "border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20",
                          ].join(" ")}
                        >
                          {u.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-5 py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                      No users found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
