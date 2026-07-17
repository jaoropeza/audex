import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "../utils/api";

const fieldCls = "block w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400";
const labelCls = "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1";

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function SpeakersManager() {
  const [profiles,   setProfiles]   = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [err,        setErr]        = useState(null);

  const [name,       setName]       = useState("");
  const [file,       setFile]       = useState(null);
  const [uploading,  setUploading]  = useState(false);
  const [uploadErr,  setUploadErr]  = useState(null);
  const [uploadOk,   setUploadOk]   = useState(false);
  const [showForm,   setShowForm]   = useState(false);

  const [deletingName, setDeletingName] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const res = await apiFetch("/api/speakers");
      if (!res.ok) throw new Error("Failed to load speaker profiles");
      setProfiles(await res.json());
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleUpload(e) {
    e.preventDefault();
    if (!name.trim() || !file) return;
    setUploading(true); setUploadErr(null); setUploadOk(false);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await apiFetch(`/api/speakers?name=${encodeURIComponent(name.trim())}`, {
        method: "POST",
        body:   form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setUploadOk(true);
      setName("");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      setShowForm(false);
      await load();
    } catch (e) {
      setUploadErr(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(profileName) {
    if (!confirm(`Delete profile "${profileName}"?`)) return;
    setDeletingName(profileName);
    try {
      await apiFetch(`/api/speakers/${encodeURIComponent(profileName)}`, { method: "DELETE" });
      setProfiles((prev) => prev.filter((p) => p.name !== profileName));
    } finally {
      setDeletingName(null);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin">
      <div className="p-5 max-w-2xl mx-auto w-full space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Speaker Profiles</h2>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              Upload short voice samples so diarization labels speakers by name instead of SPEAKER_00.
            </p>
          </div>
          {!showForm && (
            <button
              onClick={() => { setShowForm(true); setUploadErr(null); setUploadOk(false); }}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-md px-3 py-1.5 font-medium transition-colors whitespace-nowrap"
            >
              + Add profile
            </button>
          )}
        </div>

        {/* Requirements notice */}
        <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-4 py-3 text-xs text-amber-700 dark:text-amber-300 space-y-1">
          <p className="font-semibold">Requirements</p>
          <ul className="list-disc list-inside space-y-0.5 text-amber-600 dark:text-amber-400">
            <li><code>HF_TOKEN</code> must be set on the server (pyannote/embedding access)</li>
            <li>WAV file: mono or stereo, any sample rate, 5–30 seconds recommended</li>
            <li>Record the speaker in a quiet environment for best results</li>
          </ul>
        </div>

        {/* Upload form */}
        {showForm && (
          <form
            onSubmit={handleUpload}
            className="space-y-3 p-4 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-900/10"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Speaker name *</label>
                <input
                  className={fieldCls}
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alice"
                  autoFocus
                />
              </div>
              <div>
                <label className={labelCls}>WAV file *</label>
                <input
                  ref={fileRef}
                  className={fieldCls}
                  type="file"
                  accept=".wav,audio/wav,audio/x-wav"
                  required
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </div>
            </div>

            {uploadErr && (
              <p className="text-xs text-red-600 dark:text-red-400">{uploadErr}</p>
            )}

            <div className="flex gap-2 items-center">
              <button
                type="submit"
                disabled={uploading || !name.trim() || !file}
                className="text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-md px-4 py-1.5 font-medium transition-colors inline-flex items-center gap-1.5"
              >
                {uploading && (
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                {uploading ? "Extracting embedding…" : "Upload & save"}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setUploadErr(null); setName(""); setFile(null); }}
                className="text-xs rounded-md px-4 py-1.5 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              {uploading && (
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  This may take 15–30 s on first use (model download)…
                </span>
              )}
            </div>
          </form>
        )}

        {err && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-300">
            {err}
          </div>
        )}

        {/* Profile list */}
        {loading ? (
          <div className="flex items-center justify-center py-8 text-gray-400 dark:text-gray-500">
            <div className="flex items-center gap-2 text-sm">
              <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              Loading…
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {profiles.map((p) => (
              <div
                key={p.name}
                className="flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 group hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-indigo-600 dark:text-indigo-300 font-semibold text-sm shrink-0">
                  {p.name[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{p.name}</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Added {formatDate(p.created_at)}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(p.name)}
                  disabled={deletingName === p.name}
                  className="text-xs px-2.5 py-1 rounded border border-red-200 dark:border-red-800 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-40"
                >
                  {deletingName === p.name ? "…" : "Delete"}
                </button>
              </div>
            ))}

            {profiles.length === 0 && !showForm && (
              <div className="text-center py-10 text-sm text-gray-400 dark:text-gray-500">
                <p className="mb-2">No speaker profiles yet.</p>
                <p className="text-xs">
                  Add profiles so diarization uses real names instead of SPEAKER_00, SPEAKER_01, etc.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
