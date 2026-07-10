import { useState, useEffect, useRef } from "react";
import TranscriptLine from "./TranscriptLine";
import SummarizeModal from "./SummarizeModal";
import TranslateModal from "./TranslateModal";
import { useTranslation } from "../hooks/useTranslation";

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

// ── Tag Editor ────────────────────────────────────────────────────────────────

function TagEditor({ filename }) {
  const [tags, setTags] = useState([]);
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!filename) return;
    fetch(`/api/transcripts/${encodeURIComponent(filename)}/tags`)
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
      const res = await fetch(`/api/transcripts/${encodeURIComponent(filename)}/tags`, {
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
  const [sourceLang, setSourceLang] = useState("Auto");
  const [targetLang, setTargetLang] = useState("English");
  const [promptTemplate, setPromptTemplate] = useState(null);
  const [showTranslateModal, setShowTranslateModal] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [activeTab, setActiveTab] = useState("transcript");

  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummarizeModal, setShowSummarizeModal] = useState(false);
  const [audioInfo, setAudioInfo] = useState(null); // null=loading, false=none, object=exists

  const { translations, translating, error: translateError } = useTranslation(
    lines, sourceLang, targetLang, promptTemplate, translateEnabled
  );

  useEffect(() => {
    if (!filename) return;
    setLoading(true);
    setLines([]);
    setSearchResults(null);
    setSummary(null);
    setAudioInfo(null);
    setActiveTab("transcript");
    // Check for paired audio file
    fetch(`/api/transcripts/${encodeURIComponent(filename)}/audio/info`)
      .then((r) => r.ok ? r.json() : { exists: false })
      .then((d) => setAudioInfo(d.exists ? d : false))
      .catch(() => setAudioInfo(false));
    fetch(`/api/transcripts/${encodeURIComponent(filename)}`)
      .then((r) => r.json())
      .then(({ lines: l }) => { setLines(l); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filename]);

  useEffect(() => {
    if (activeTab !== "summary" || !filename || summary !== null) return;
    setSummaryLoading(true);
    fetch(`/api/transcripts/${encodeURIComponent(filename)}/summary`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { setSummary(data ? data.summary_text : ""); setSummaryLoading(false); })
      .catch(() => { setSummary(""); setSummaryLoading(false); });
  }, [activeTab, filename]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!search.trim()) { setSearchResults(null); return; }
    const res = await fetch(
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
          {displayLines.map((line, i) => (
            <TranscriptLine
              key={i}
              raw={line}
              translation={translateEnabled ? translations[line] : null}
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
