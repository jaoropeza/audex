import { useState, useEffect, useCallback, useRef } from "react";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const TAG_COLORS = [
  "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300",
  "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300",
  "bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300",
  "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300",
  "bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300",
  "bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300",
];

function tagColor(tag) {
  let h = 0;
  for (let i = 0; i < tag.length; i++) h = (h * 31 + tag.charCodeAt(i)) & 0xffff;
  return TAG_COLORS[h % TAG_COLORS.length];
}

function TagPill({ tag, active, onClick }) {
  return (
    <span
      onClick={onClick}
      className={[
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium cursor-pointer select-none transition-all",
        tagColor(tag),
        active ? "ring-1 ring-current" : "opacity-75 hover:opacity-100",
      ].join(" ")}
    >
      {tag}
    </span>
  );
}

export default function TranscriptList({ selected, onSelect, onLive, liveFile }) {
  const [files, setFiles] = useState([]);
  const [nameFilter, setNameFilter] = useState("");
  const [deleting, setDeleting] = useState(null);
  const [activeTag, setActiveTag] = useState(null);

  // Semantic search
  const [searchMode, setSearchMode] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef(null);

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

  // Debounced semantic search
  useEffect(() => {
    if (!searchMode) return;
    clearTimeout(searchTimer.current);
    if (!searchQuery.trim()) { setSearchResults([]); return; }
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`/api/db/search?q=${encodeURIComponent(searchQuery)}&n=10`);
        const data = await res.json();
        setSearchResults(data.results || []);
      } catch { setSearchResults([]); }
      finally { setSearching(false); }
    }, 400);
    return () => clearTimeout(searchTimer.current);
  }, [searchQuery, searchMode]);

  // Collect all tags
  const allTags = [...new Set(files.flatMap((f) => f.tags || []))].sort();

  // Filter file list
  const filtered = files.filter((f) => {
    const nameOk = f.name.toLowerCase().includes(nameFilter.toLowerCase());
    const tagOk  = activeTag == null || (f.tags || []).includes(activeTag);
    return nameOk && tagOk;
  });

  async function handleDelete(e, name) {
    e.stopPropagation();
    if (!confirm(`Delete "${name}"?`)) return;
    setDeleting(name);
    await fetch(`/api/transcripts/${encodeURIComponent(name)}`, { method: "DELETE" });
    setDeleting(null);
    load();
  }

  function toggleSearchMode() {
    setSearchMode((s) => !s);
    setSearchQuery("");
    setSearchResults([]);
    setNameFilter("");
    setActiveTag(null);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Transcripts
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleSearchMode}
            title={searchMode ? "Browse files" : "Semantic search"}
            className={[
              "text-sm p-0.5 rounded transition-colors",
              searchMode
                ? "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20"
                : "text-gray-400 hover:text-gray-600 dark:hover:text-gray-200",
            ].join(" ")}
          >
            🔍
          </button>
          {!searchMode && (
            <button
              onClick={load}
              title="Refresh"
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors text-base leading-none p-0.5 rounded"
            >
              ↻
            </button>
          )}
        </div>
      </div>

      {/* Search bar */}
      <div className="px-3 py-2 shrink-0">
        <input
          type="search"
          placeholder={searchMode ? "Semantic search…" : "Filter by name…"}
          value={searchMode ? searchQuery : nameFilter}
          onChange={(e) => searchMode ? setSearchQuery(e.target.value) : setNameFilter(e.target.value)}
          className="w-full text-xs rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        {searchMode && (
          <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">
            Searches transcript content using AI embeddings
          </p>
        )}
      </div>

      {/* Tag filter chips (browse mode only) */}
      {!searchMode && allTags.length > 0 && (
        <div className="px-3 pb-1.5 flex flex-wrap gap-1 shrink-0">
          {allTags.map((tag) => (
            <TagPill
              key={tag}
              tag={tag}
              active={activeTag === tag}
              onClick={() => setActiveTag(activeTag === tag ? null : tag)}
            />
          ))}
        </div>
      )}

      {/* ── Semantic search results ── */}
      {searchMode && (
        <ul className="flex-1 overflow-y-auto scrollbar-thin">
          {searching && (
            <li className="px-3 py-3 text-center text-xs text-gray-400 dark:text-gray-500">
              Searching…
            </li>
          )}
          {!searching && searchQuery.trim() && searchResults.length === 0 && (
            <li className="px-3 py-6 text-center text-xs text-gray-400 dark:text-gray-500">
              No matches found
            </li>
          )}
          {!searching && searchResults.map((r, i) => (
            <li
              key={i}
              onClick={() => onSelect(r.filename)}
              className={[
                "px-3 py-2.5 cursor-pointer border-l-2 transition-colors",
                selected === r.filename
                  ? "bg-blue-50 dark:bg-blue-900/20 border-blue-500"
                  : "border-transparent hover:bg-gray-100 dark:hover:bg-gray-700/50",
              ].join(" ")}
            >
              <div className="text-xs font-medium truncate text-gray-900 dark:text-gray-100">
                {r.filename.replace(/\.txt$/, "")}
              </div>
              <div className="mt-0.5 text-[10px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                {r.text}
              </div>
              <div className="mt-0.5 text-[10px] text-gray-400 dark:text-gray-500">
                score {(r.score * 100).toFixed(0)}%
              </div>
            </li>
          ))}
          {!searchQuery.trim() && (
            <li className="px-3 py-6 text-center text-xs text-gray-400 dark:text-gray-500">
              Type to search across all transcript content
            </li>
          )}
        </ul>
      )}

      {/* ── File list ── */}
      {!searchMode && (
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
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium truncate leading-snug">
                      {f.name.replace(/\.txt$/, "")}
                    </span>
                    {f.has_summary && (
                      <span title="Has summary" className="text-[9px] text-emerald-600 dark:text-emerald-400 shrink-0">✦</span>
                    )}
                  </div>
                  <div className="flex justify-between mt-0.5">
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                      {formatDate(f.modified_iso)}
                    </span>
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                      {f.line_count}L · {formatSize(f.size_bytes)}
                    </span>
                  </div>
                  {f.tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {f.tags.map((tag) => (
                        <TagPill
                          key={tag}
                          tag={tag}
                          active={activeTag === tag}
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveTag(activeTag === tag ? null : tag);
                          }}
                        />
                      ))}
                    </div>
                  )}
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
      )}
    </div>
  );
}
