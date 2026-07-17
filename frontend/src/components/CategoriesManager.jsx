import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../utils/api";

const PALETTE = [
  "#6366f1", "#3b82f6", "#06b6d4", "#10b981",
  "#f59e0b", "#ef4444", "#ec4899", "#8b5cf6",
  "#64748b", "#0ea5e9",
];

function ColorDot({ color, size = "md" }) {
  const sz = size === "sm" ? "w-3 h-3" : "w-4 h-4";
  return <span className={`inline-block rounded-full shrink-0 ${sz}`} style={{ backgroundColor: color }} />;
}

function ColorPicker({ value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {PALETTE.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={[
            "w-6 h-6 rounded-full transition-transform hover:scale-110 focus:outline-none",
            value === c ? "ring-2 ring-offset-2 ring-blue-500 scale-110" : "",
          ].join(" ")}
          style={{ backgroundColor: c }}
          title={c}
        />
      ))}
    </div>
  );
}

const fieldCls = "block w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400";
const labelCls = "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1";

const EMPTY = { name: "", description: "", color: PALETTE[0] };

function CategoryForm({ initial = EMPTY, onSave, onCancel, saving, error }) {
  const [form, setForm] = useState(initial);
  function set(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  return (
    <div className="space-y-3 p-4 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-900/10">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Name *</label>
          <input
            className={fieldCls}
            required
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="Meetings"
            autoFocus
          />
        </div>
        <div>
          <label className={labelCls}>Description</label>
          <input
            className={fieldCls}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="Optional description"
          />
        </div>
      </div>
      <div>
        <label className={labelCls}>Color</label>
        <ColorPicker value={form.color} onChange={(c) => set("color", c)} />
      </div>
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={saving || !form.name.trim()}
          onClick={() => onSave(form)}
          className="text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-md px-4 py-1.5 font-medium transition-colors inline-flex items-center gap-1.5"
        >
          {saving && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs rounded-md px-4 py-1.5 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function CategoriesManager() {
  const [cats,    setCats]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [err,     setErr]     = useState(null);

  const [creating,   setCreating]   = useState(false);
  const [createErr,  setCreateErr]  = useState(null);
  const [savingNew,  setSavingNew]  = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const [editId,    setEditId]    = useState(null);
  const [editErr,   setEditErr]   = useState(null);
  const [savingEdit,setSavingEdit]= useState(false);

  const [deletingId, setDeletingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const res = await apiFetch("/api/categories");
      if (!res.ok) throw new Error("Failed to load categories");
      setCats(await res.json());
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(form) {
    setSavingNew(true); setCreateErr(null);
    try {
      const res = await apiFetch("/api/categories", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      setShowCreate(false);
      await load();
    } catch (e) {
      setCreateErr(e.message);
    } finally {
      setSavingNew(false);
    }
  }

  async function handleEdit(form) {
    setSavingEdit(true); setEditErr(null);
    try {
      const res = await apiFetch(`/api/categories/${editId}`, {
        method:  "PUT",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      setEditId(null);
      await load();
    } catch (e) {
      setEditErr(e.message);
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this category? Assignments will also be removed.")) return;
    setDeletingId(id);
    try {
      await apiFetch(`/api/categories/${id}`, { method: "DELETE" });
      setCats((prev) => prev.filter((c) => c.id !== id));
    } finally {
      setDeletingId(null);
    }
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

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin">
      <div className="p-5 max-w-2xl mx-auto w-full space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Categories</h2>
          {!showCreate && (
            <button
              onClick={() => setShowCreate(true)}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-md px-3 py-1.5 font-medium transition-colors"
            >
              + New category
            </button>
          )}
        </div>

        {err && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-300">
            {err}
          </div>
        )}

        {showCreate && (
          <CategoryForm
            onSave={handleCreate}
            onCancel={() => { setShowCreate(false); setCreateErr(null); }}
            saving={savingNew}
            error={createErr}
          />
        )}

        {/* Category list */}
        <div className="space-y-2">
          {cats.map((cat) =>
            editId === cat.id ? (
              <CategoryForm
                key={cat.id}
                initial={{ name: cat.name, description: cat.description || "", color: cat.color }}
                onSave={handleEdit}
                onCancel={() => { setEditId(null); setEditErr(null); }}
                saving={savingEdit}
                error={editErr}
              />
            ) : (
              <div
                key={cat.id}
                className="flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 group hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                <ColorDot color={cat.color} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{cat.name}</p>
                  {cat.description && (
                    <p className="text-xs text-gray-400 dark:text-gray-500 truncate">{cat.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => { setEditId(cat.id); setEditErr(null); }}
                    className="text-xs px-2.5 py-1 rounded border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(cat.id)}
                    disabled={deletingId === cat.id}
                    className="text-xs px-2.5 py-1 rounded border border-red-200 dark:border-red-800 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-40"
                  >
                    {deletingId === cat.id ? "…" : "Delete"}
                  </button>
                </div>
              </div>
            )
          )}
          {cats.length === 0 && !showCreate && (
            <div className="text-center py-12 text-sm text-gray-400 dark:text-gray-500">
              No categories yet. Create one to start organizing your transcripts.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
