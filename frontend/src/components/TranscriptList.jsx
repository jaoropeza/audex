import { useState, useEffect, useCallback } from "react";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function TranscriptList({ selected, onSelect, onLive, liveFile }) {
  const [files, setFiles] = useState([]);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/transcripts");
      const { files: f } = await res.json();
      setFiles(f);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const filtered = files.filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  );

  async function handleDelete(e, name) {
    e.stopPropagation();
    if (!confirm(`Delete "${name}"?`)) return;
    setDeleting(name);
    await fetch(`/api/transcripts/${encodeURIComponent(name)}`, { method: "DELETE" });
    setDeleting(null);
    load();
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Transcripts
        </span>
        <button
          onClick={load}
          title="Refresh"
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors text-base leading-none p-0.5 rounded"
        >
          ↻
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 shrink-0">
        <input
          type="search"
          placeholder="Filter transcripts…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full text-xs rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* List */}
      <ul className="flex-1 overflow-y-auto scrollbar-thin">
        {filtered.map((f) => {
          const isActive = selected === f.name;
          const isLive = liveFile === f.name;
          return (
            <li
              key={f.name}
              onClick={() => onSelect(f.name)}
              className={[
                "relative px-3 py-2.5 cursor-pointer border-l-2 transition-colors group",
                isActive
                  ? "bg-blue-50 dark:bg-blue-900/20 border-blue-500 text-gray-900 dark:text-white"
                  : "border-transparent hover:bg-gray-100 dark:hover:bg-gray-700/50 text-gray-700 dark:text-gray-300",
              ].join(" ")}
            >
              <div className="pr-6">
                <div className="text-xs font-medium truncate leading-snug">
                  {f.name.replace(/\.txt$/, "")}
                </div>
                <div className="flex justify-between mt-0.5">
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">
                    {formatDate(f.modified_iso)}
                  </span>
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">
                    {f.line_count}L · {formatSize(f.size_bytes)}
                  </span>
                </div>
              </div>

              {isLive && (
                <span className="absolute top-2 right-7 bg-red-500 text-white text-[9px] font-bold px-1 py-0.5 rounded leading-none">
                  LIVE
                </span>
              )}

              <button
                onClick={(e) => handleDelete(e, f.name)}
                disabled={deleting === f.name}
                title="Delete"
                className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-all text-sm disabled:opacity-30"
              >
                🗑
              </button>
            </li>
          );
        })}
        {filtered.length === 0 && (
          <li className="px-3 py-6 text-center text-xs text-gray-400 dark:text-gray-500">
            No transcripts found
          </li>
        )}
      </ul>
    </div>
  );
}
