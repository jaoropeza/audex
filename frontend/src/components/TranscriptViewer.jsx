import { useState, useEffect, useRef } from "react";
import { apiFetch } from "../utils/api";
import TranscriptLine from "./TranscriptLine";
import SummarizeModal from "./SummarizeModal";
import TranslateModal from "./TranslateModal";
import { useTranslation } from "../hooks/useTranslation";
import { parseLine } from "./TranscriptLine";

const inputCls = "rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400";
const btnCls   = "rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500";

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

// ── Group Picker ──────────────────────────────────────────────────────────────

const GROUP_PRESETS = [
  { label: "None", value: null },
  { label: "30 s", value: 30 },
  { label: "1 min", value: 60 },
  { label: "5 min", value: 300 },
];

function GroupPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    function handle(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    if (open) document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  const label = value == null ? "Group" : value >= 60 ? `${value / 60} min` : `${value} s`;
  const active = value != null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={[
          "flex items-center gap-1 text-xs px-2 py-1 rounded-md border transition-colors",
          active || open
            ? "border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300"
            : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-700",
        ].join(" ")}
        title="Group transcript lines by time window"
      >
        ⏱ {label}
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-20 w-52 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg p-3">
          <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Group by time window</p>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {GROUP_PRESETS.map((p) => (
              <button
                key={String(p.value)}
                onClick={() => { onChange(p.value); if (p.value !== null) setOpen(false); if (p.value === null) setOpen(false); }}
                className={[
                  "px-2.5 py-1 rounded-full text-xs font-medium border transition-colors",
                  value === p.value
                    ? "bg-blue-600 border-blue-600 text-white"
                    : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-700 hover:border-blue-400",
                ].join(" ")}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <input
              type="number"
              min={5}
              max={3600}
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder="Custom (sec)"
              className="flex-1 text-xs rounded border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-gray-400"
            />
            <button
              onClick={() => { const v = parseInt(custom, 10); if (v > 0) { onChange(v); setOpen(false); } }}
              className="px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium"
            >
              Set
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Download helpers ──────────────────────────────────────────────────────────

function tsToSecs(ts) {
  const [h, m, s] = ts.split(":").map(Number);
  return h * 3600 + m * 60 + s;
}
function secsToVTT(secs) {
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.000`;
}
function secsToSRT(secs) {
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")},000`;
}
function extractTs(raw) { const m = raw.match(/^\[(\d{2}:\d{2}:\d{2})\]/); return m ? m[1] : null; }

function linesToVTT(filename, lines) {
  const cues = [];
  for (let i = 0; i < lines.length; i++) {
    const ts = extractTs(lines[i]);
    if (!ts) continue;
    const { speaker, text } = parseLine(lines[i]);
    if (!text) continue;
    const start = tsToSecs(ts);
    let end = start + 3;
    for (let j = i + 1; j < lines.length; j++) { const nts = extractTs(lines[j]); if (nts) { end = tsToSecs(nts); break; } }
    cues.push(`${secsToVTT(start)} --> ${secsToVTT(end)}\n${speaker ? `${speaker}: ` : ""}${text}`);
  }
  return `WEBVTT\nNOTE ${filename}\n\n${cues.join("\n\n")}`;
}
function linesToSRT(filename, lines) {
  const cues = [];
  let idx = 1;
  for (let i = 0; i < lines.length; i++) {
    const ts = extractTs(lines[i]);
    if (!ts) continue;
    const { speaker, text } = parseLine(lines[i]);
    if (!text) continue;
    const start = tsToSecs(ts);
    let end = start + 3;
    for (let j = i + 1; j < lines.length; j++) { const nts = extractTs(lines[j]); if (nts) { end = tsToSecs(nts); break; } }
    cues.push(`${idx}\n${secsToSRT(start)} --> ${secsToSRT(end)}\n${speaker ? `${speaker}: ` : ""}${text}`);
    idx++;
  }
  return cues.join("\n\n");
}
function triggerDownload(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

// ── Download Menu ─────────────────────────────────────────────────────────────

function DownloadMenu({ filename, lines }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const base = filename.replace(/\.txt$/, "");

  useEffect(() => {
    function handle(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    if (open) document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  function downloadAs(fmt) {
    setOpen(false);
    if (fmt === "txt") triggerDownload(lines.join("\n"), `${base}.txt`, "text/plain");
    else if (fmt === "vtt") triggerDownload(linesToVTT(filename, lines), `${base}.vtt`, "text/vtt");
    else if (fmt === "srt") triggerDownload(linesToSRT(filename, lines), `${base}.srt`, "text/plain");
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={lines.length === 0}
        title="Export transcript"
        className="flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ↓ Export
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 w-40 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg overflow-hidden">
          {[["txt", "Plain text (.txt)"], ["vtt", "WebVTT (.vtt)"], ["srt", "SubRip (.srt)"]].map(([fmt, label]) => (
            <button
              key={fmt}
              onClick={() => downloadAs(fmt)}
              className="w-full text-left px-3 py-2 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Category Picker ───────────────────────────────────────────────────────────

function CategoryPicker({ filename }) {
  const [cats,     setCats]     = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [open,     setOpen]     = useState(false);
  const [saving,   setSaving]   = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!filename) return;
    apiFetch("/api/categories").then((r) => r.ok ? r.json() : []).then(setCats).catch(() => {});
    apiFetch(`/api/transcripts/${encodeURIComponent(filename)}/categories`)
      .then((r) => r.ok ? r.json() : [])
      .then((assigned) => setSelected(new Set(assigned.map((c) => c.id))))
      .catch(() => {});
  }, [filename]);

  useEffect(() => {
    function handle(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    if (open) document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  async function toggleCat(id) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
    setSaving(true);
    try {
      await apiFetch(`/api/transcripts/${encodeURIComponent(filename)}/categories`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_ids: [...next] }),
      });
    } finally { setSaving(false); }
  }

  if (cats.length === 0) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        title="Categories"
        className={[
          "flex items-center gap-1 text-xs px-2 py-1 rounded-md border transition-colors",
          open || selected.size > 0
            ? "border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300"
            : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500",
        ].join(" ")}
      >
        📂 {selected.size > 0 ? <span>{selected.size}</span> : null}
        {saving && <span className="w-2.5 h-2.5 border border-current border-t-transparent rounded-full animate-spin" />}
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 z-20 w-52 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg p-2">
          <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5 px-1">
            Assign categories
          </p>
          {cats.map((cat) => (
            <label
              key={cat.id}
              className="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <input
                type="checkbox"
                checked={selected.has(cat.id)}
                onChange={() => toggleCat(cat.id)}
                className="w-3.5 h-3.5 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
              />
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: cat.color }} />
              <span className="text-xs text-gray-700 dark:text-gray-200 truncate">{cat.name}</span>
            </label>
          ))}
          {cats.length === 0 && (
            <p className="text-[10px] text-gray-400 px-2 py-1">No categories — create them in the Categories tab.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Tag Editor ────────────────────────────────────────────────────────────────

function TagEditor({ filename }) {
  const [tags, setTags] = useState([]);
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!filename) return;
    apiFetch(`/api/transcripts/${encodeURIComponent(filename)}/tags`)
      .then((r) => r.ok ? r.json() : { tags: [] })
      .then((d) => setTags(d.tags || []))
      .catch(() => setTags([]));
  }, [filename]);

  // Close on outside click
  useEffect(() => {
    function handle(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    if (open) document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  async function save(newTags) {
    setSaving(true);
    try {
      const res = await apiFetch(`/api/transcripts/${encodeURIComponent(filename)}/tags`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags: newTags }),
      });
      if (res.ok) {
        const d = await res.json();
        setTags(d.tags || []);
      }
    } finally { setSaving(false); }
  }

  function addTag(e) {
    e.preventDefault();
    const tag = input.trim().toLowerCase();
    if (!tag || tags.includes(tag)) { setInput(""); return; }
    const next = [...tags, tag];
    setInput("");
    save(next);
  }

  function removeTag(tag) {
    save(tags.filter((t) => t !== tag));
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        title="Tags"
        className={[
          "flex items-center gap-1 text-xs px-2 py-1 rounded-md border transition-colors",
          open
            ? "border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300"
            : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500",
        ].join(" ")}
      >
        🏷 <span>{tags.length > 0 ? tags.length : "Tags"}</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-20 w-64 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg p-3">
          {/* Current tags */}
          <div className="flex flex-wrap gap-1 mb-2 min-h-[24px]">
            {tags.length === 0 && (
              <span className="text-[10px] text-gray-400 dark:text-gray-500">No tags yet</span>
            )}
            {tags.map((tag) => (
              <span
                key={tag}
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${tagColor(tag)}`}
              >
                {tag}
                <button
                  onClick={() => removeTag(tag)}
                  className="hover:opacity-60 transition-opacity leading-none"
                >×</button>
              </span>
            ))}
          </div>
          {/* Add tag input */}
          <form onSubmit={addTag} className="flex gap-1">
            <input
              autoFocus
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Add tag…"
              className="flex-1 text-xs rounded border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-gray-400"
            />
            <button
              type="submit"
              disabled={saving}
              className="px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50"
            >
              +
            </button>
          </form>
          <p className="mt-1.5 text-[10px] text-gray-400 dark:text-gray-500">Press Enter to add · click × to remove</p>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TranscriptViewer({ filename }) {
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [translateEnabled, setTranslateEnabled] = useState(false);
  const [sourceLang,    setSourceLang]    = useState("Auto");
  const [targetLang,    setTargetLang]    = useState("English");
  const [promptTemplate, setPromptTemplate] = useState(null);
  const [groupSeconds,  setGroupSeconds]  = useState(null);
  const [showTranslateModal, setShowTranslateModal] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [activeTab, setActiveTab] = useState("transcript");

  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummarizeModal, setShowSummarizeModal] = useState(false);
  const [audioInfo, setAudioInfo] = useState(null); // null=loading, false=none, object=exists
  const [error, setError] = useState(null);

  const { translations, groups, translating, error: translateError } = useTranslation(
    lines, sourceLang, targetLang, promptTemplate, groupSeconds, translateEnabled
  );

  useEffect(() => {
    if (!filename) return;
    setLoading(true);
    setLines([]);
    setSearchResults(null);
    setSummary(null);
    setAudioInfo(null);
    setError(null);
    setActiveTab("transcript");
    // Check for paired audio file
    apiFetch(`/api/transcripts/${encodeURIComponent(filename)}/audio/info`)
      .then((r) => r.ok ? r.json() : { exists: false })
      .then((d) => setAudioInfo(d.exists ? d : false))
      .catch(() => setAudioInfo(false));
    apiFetch(`/api/transcripts/${encodeURIComponent(filename)}`)
      .then(async (r) => {
        if (!r.ok) {
          const detail = await r.json().then((d) => d.detail || r.statusText).catch(() => r.statusText);
          setError(`Error ${r.status}: ${detail}`);
          setLoading(false);
          return;
        }
        const { lines: l } = await r.json();
        setLines(l);
        setLoading(false);
      })
      .catch((err) => { setError(err.message || "Failed to load transcript"); setLoading(false); });
  }, [filename]);

  useEffect(() => {
    if (activeTab !== "summary" || !filename || summary !== null) return;
    setSummaryLoading(true);
    apiFetch(`/api/transcripts/${encodeURIComponent(filename)}/summary`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { setSummary(data ? data.summary_text : ""); setSummaryLoading(false); })
      .catch(() => { setSummary(""); setSummaryLoading(false); });
  }, [activeTab, filename]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!search.trim()) { setSearchResults(null); return; }
    const res = await apiFetch(
      `/api/transcripts/${encodeURIComponent(filename)}/search?q=${encodeURIComponent(search)}`
    );
    const { matches } = await res.json();
    setSearchResults(matches);
  }

  function handleSummaryDone(summaryText) {
    setSummary(summaryText);
    setShowSummarizeModal(false);
    setActiveTab("summary");
  }

  const displayLines = searchResults ? searchResults.map((m) => m.text) : lines;

  if (!filename) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400 dark:text-gray-500">
        <div className="text-center">
          <div className="text-4xl mb-3">📄</div>
          <p className="text-sm">Select a transcript from the sidebar</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 shrink-0 flex-wrap">
        <span className="text-xs font-mono text-gray-500 dark:text-gray-400 truncate max-w-[130px]" title={filename}>
          {filename}
        </span>

        {/* Tab switcher */}
        <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 text-xs">
          <button
            onClick={() => setActiveTab("transcript")}
            className={[
              "px-3 py-1 font-medium transition-colors",
              activeTab === "transcript"
                ? "bg-blue-600 text-white"
                : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600",
            ].join(" ")}
          >
            Transcript
          </button>
          <button
            onClick={() => setActiveTab("summary")}
            className={[
              "px-3 py-1 font-medium transition-colors border-l border-gray-200 dark:border-gray-700",
              activeTab === "summary"
                ? "bg-blue-600 text-white"
                : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600",
            ].join(" ")}
          >
            Summary {summary ? "✓" : ""}
          </button>
        </div>

        {/* Tag editor (always visible) */}
        <TagEditor filename={filename} />

        {/* Category picker (always visible) */}
        <CategoryPicker filename={filename} />

        {/* Export menu (always visible, disabled until content loaded) */}
        <DownloadMenu filename={filename} lines={lines} />

        {activeTab === "transcript" && (
          <>
            <form className="flex gap-1.5 flex-1 min-w-0" onSubmit={handleSearch}>
              <input
                className={`${inputCls} flex-1 min-w-0 py-1 text-xs`}
                type="search"
                placeholder="Search…"
                value={search}
                onChange={(e) => { setSearch(e.target.value); if (!e.target.value) setSearchResults(null); }}
              />
              <button type="submit" className={`${btnCls} bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 py-1 text-xs`}>
                Search
              </button>
            </form>
            <GroupPicker value={groupSeconds} onChange={setGroupSeconds} />

            {!translateEnabled ? (
              <button
                onClick={() => setShowTranslateModal(true)}
                className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-700 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-300 transition-colors whitespace-nowrap"
              >
                🌐 Translate
              </button>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setShowTranslateModal(true)}
                  className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border border-blue-400 dark:border-blue-500 text-blue-600 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/20 transition-colors whitespace-nowrap"
                  title="Change translation settings"
                >
                  🌐 {sourceLang === "Auto" ? "Auto" : sourceLang} → {targetLang}
                  {groupSeconds ? <span className="ml-1 opacity-70">{groupSeconds >= 60 ? `${groupSeconds/60}m` : `${groupSeconds}s`}</span> : null}
                  {translating && <span className="ml-1 w-2.5 h-2.5 border border-current border-t-transparent rounded-full animate-spin" />}
                </button>
                <button
                  onClick={() => setTranslateEnabled(false)}
                  title="Disable translation"
                  className="text-gray-400 hover:text-red-500 dark:hover:text-red-400 text-xs leading-none transition-colors px-0.5"
                >
                  ✕
                </button>
              </div>
            )}
            {translateError && translateEnabled && (
              <span className="text-[10px] text-red-500 dark:text-red-400 truncate max-w-[140px]" title={translateError}>
                {translateError}
              </span>
            )}
          </>
        )}

        {activeTab === "summary" && (
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => setShowSummarizeModal(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {summary ? "↺ Re-summarize" : "✦ Generate Summary"}
            </button>
          </div>
        )}
      </div>

      {/* Audio player bar */}
      {audioInfo && (
        <div className="flex items-center gap-3 px-4 py-1.5 bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <span className="text-[10px] text-gray-400 dark:text-gray-500 shrink-0 font-mono">
            🎵 {audioInfo.filename}
          </span>
          <audio
            controls
            className="flex-1 h-7"
            src={`/api/transcripts/${encodeURIComponent(filename)}/audio`}
            style={{ minWidth: 0 }}
          />
          <a
            href={`/api/transcripts/${encodeURIComponent(filename)}/audio`}
            download={audioInfo.filename}
            title="Download audio"
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xs shrink-0"
          >
            ↓
          </a>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300 shrink-0">
          <span className="shrink-0">⚠</span>
          <span className="flex-1">{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-600 dark:hover:text-red-200 font-medium shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Search banner */}
      {activeTab === "transcript" && searchResults && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800 text-xs text-blue-700 dark:text-blue-300 shrink-0">
          <span>{searchResults.length} match{searchResults.length !== 1 ? "es" : ""} for "{search}"</span>
          <button
            onClick={() => { setSearchResults(null); setSearch(""); }}
            className="ml-auto text-blue-500 hover:text-blue-700 dark:hover:text-blue-200 font-medium"
          >
            ✕ Clear
          </button>
        </div>
      )}

      {/* ── Transcript tab ── */}
      {activeTab === "transcript" && (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {loading && (
            <div className="flex items-center justify-center py-12 text-gray-400 dark:text-gray-500 text-sm">Loading…</div>
          )}
          {!loading && displayLines.length === 0 && (
            <div className="flex items-center justify-center py-12 text-gray-400 dark:text-gray-500 text-sm">
              {searchResults ? "No matches found." : "Transcript is empty."}
            </div>
          )}

          {/* Grouped view — active whenever groupSeconds is set, with or without translation */}
          {!loading && groupSeconds && !searchResults && (
            <GroupedView
              groups={groups}
              translations={translateEnabled ? translations : {}}
              translating={translateEnabled && translating}
            />
          )}

          {/* Per-line view — when not grouped, or when a search is active */}
          {!loading && (!groupSeconds || searchResults) && displayLines.map((line, i) => (
            <TranscriptLine
              key={i}
              raw={line}
              translation={translateEnabled && !groupSeconds ? translations[line] : null}
              searchTerm={searchResults ? search : ""}
            />
          ))}
        </div>
      )}

      {/* ── Summary tab ── */}
      {activeTab === "summary" && (
        <div className="flex-1 overflow-y-auto scrollbar-thin p-5">
          {summaryLoading && (
            <div className="flex items-center justify-center py-12 text-gray-400 dark:text-gray-500 text-sm">
              <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
              Loading summary…
            </div>
          )}
          {!summaryLoading && summary === "" && (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 dark:text-gray-500">
              <div className="text-4xl mb-3">📝</div>
              <p className="text-sm mb-4">No summary yet for this transcript.</p>
              <button
                onClick={() => setShowSummarizeModal(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                ✦ Generate Summary
              </button>
            </div>
          )}
          {!summaryLoading && summary && (
            <div className="max-w-3xl mx-auto">
              <SummaryContent text={summary} />
            </div>
          )}
        </div>
      )}

      {showSummarizeModal && (
        <SummarizeModal
          filename={filename}
          lineCount={lines.length}
          onClose={() => setShowSummarizeModal(false)}
          onDone={handleSummaryDone}
        />
      )}

      {showTranslateModal && (
        <TranslateModal
          lineCount={lines.length}
          initialSource={sourceLang}
          initialTarget={targetLang}
          initialPrompt={promptTemplate || ""}
          onClose={() => setShowTranslateModal(false)}
          onApply={({ sourceLang: sl, targetLang: tl, promptTemplate: pt }) => {
            setSourceLang(sl);
            setTargetLang(tl);
            setPromptTemplate(pt);
            setTranslateEnabled(true);
            setShowTranslateModal(false);
          }}
        />
      )}
    </div>
  );
}

// ── Grouped transcript view ───────────────────────────────────────────────────

function extractTimestamp(raw) {
  const m = raw.match(/\[(\d{2}:\d{2}:\d{2})\]/);
  return m ? m[1] : null;
}

function GroupedView({ groups, translations, translating }) {
  return (
    <>
      {groups.map((group) => {
        const translation = translations[group.key];
        const firstTs = extractTimestamp(group.lines[0]);
        const lastTs  = extractTimestamp(group.lines[group.lines.length - 1]);
        const pending = !translation && translating;
        const text    = group.lines.map((l) => parseLine(l).text).join(" ");

        return (
          <div key={group.key} className="border-b border-gray-100 dark:border-gray-800/60 px-4 py-2.5">
            {/* Time-range header */}
            {firstTs && (
              <span className="font-mono text-[10px] text-gray-400 dark:text-gray-500 block mb-1">
                {firstTs}{lastTs && lastTs !== firstTs ? ` — ${lastTs}` : ""}
              </span>
            )}

            {/* Joined paragraph */}
            <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">{text}</p>

            {/* Group-level translation block */}
            {(translation || pending) && (
              <div className="mt-2 px-3 py-2 rounded-md bg-blue-50 dark:bg-blue-900/20 border-l-2 border-blue-400 dark:border-blue-600">
                {pending ? (
                  <span className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                    <span className="w-2.5 h-2.5 border border-current border-t-transparent rounded-full animate-spin shrink-0" />
                    Translating…
                  </span>
                ) : (
                  <p className="text-sm text-blue-800 dark:text-blue-200 leading-relaxed">{translation}</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

// ── Summary renderer ──────────────────────────────────────────────────────────

function parseSummary(text) {
  // Line-by-line parser — robust against leading blank lines, \r\n, extra spaces
  const sections = [];
  let current = null;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd();
    const trimmed = line.trim();

    if (/^#{1,3} /.test(trimmed)) {
      // New heading — commit previous section
      if (current) sections.push(current);
      current = { heading: trimmed.replace(/^#{1,3} /, "").trim(), lines: [] };
    } else {
      if (!current) {
        // Content before any heading — create a headingless section
        if (trimmed) {
          current = { heading: null, lines: [line] };
        }
      } else {
        current.lines.push(line);
      }
    }
  }
  if (current) sections.push(current);
  return sections;
}

function SummaryContent({ text }) {
  const sections = parseSummary(text);

  if (sections.length === 0) {
    return <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{text}</p>;
  }

  return (
    <div className="space-y-4">
      {sections.map((section, i) => {
        const bodyLines = section.lines.filter((l, idx, arr) => {
          // Trim leading and trailing blank lines within a section
          if (!l.trim()) {
            const hasContentBefore = arr.slice(0, idx).some((x) => x.trim());
            const hasContentAfter  = arr.slice(idx + 1).some((x) => x.trim());
            return hasContentBefore && hasContentAfter;
          }
          return true;
        });

        return (
          <div key={i} className="rounded-lg border border-gray-100 dark:border-gray-700 overflow-hidden">
            {section.heading && (
              <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700">
                <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">{section.heading}</h3>
              </div>
            )}
            <div className="px-4 py-3 space-y-1">
              {bodyLines.map((line, j) => {
                if (!line.trim()) return <div key={j} className="h-1" />;
                const isBullet = /^[\-*•]\s/.test(line.trimStart());
                if (isBullet) {
                  return (
                    <div key={j} className="flex gap-2 text-sm text-gray-700 dark:text-gray-300">
                      <span className="text-gray-400 shrink-0 mt-0.5">•</span>
                      <span>{line.replace(/^[\s\-*•]+/, "")}</span>
                    </div>
                  );
                }
                return <p key={j} className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{line}</p>;
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
