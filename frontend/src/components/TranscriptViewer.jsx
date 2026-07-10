import { useState, useEffect } from "react";
import TranscriptLine from "./TranscriptLine";
import SummarizeModal from "./SummarizeModal";
import { useTranslation } from "../hooks/useTranslation";

const LANGUAGES = ["English", "Spanish", "French", "Portuguese", "German", "Italian", "Japanese", "Chinese"];

const inputCls = "rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400";
const btnCls   = "rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500";

export default function TranscriptViewer({ filename }) {
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [translateEnabled, setTranslateEnabled] = useState(false);
  const [targetLang, setTargetLang] = useState("English");
  const [searchResults, setSearchResults] = useState(null);
  const [activeTab, setActiveTab] = useState("transcript");

  // Summary state
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummarizeModal, setShowSummarizeModal] = useState(false);

  const { translations } = useTranslation(lines, targetLang, translateEnabled);

  useEffect(() => {
    if (!filename) return;
    setLoading(true);
    setLines([]);
    setSearchResults(null);
    setSummary(null);
    fetch(`/api/transcripts/${encodeURIComponent(filename)}`)
      .then((r) => r.json())
      .then(({ lines: l }) => { setLines(l); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filename]);

  // Load existing summary when switching to summary tab
  useEffect(() => {
    if (activeTab !== "summary" || !filename || summary !== null) return;
    setSummaryLoading(true);
    fetch(`/api/transcripts/${encodeURIComponent(filename)}/summary`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        setSummary(data ? data.summary_text : "");
        setSummaryLoading(false);
      })
      .catch(() => {
        setSummary("");
        setSummaryLoading(false);
      });
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
        <span className="text-xs font-mono text-gray-500 dark:text-gray-400 truncate max-w-[140px]" title={filename}>
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

        {activeTab === "transcript" && (
          <>
            <form className="flex gap-1.5 flex-1 min-w-0" onSubmit={handleSearch}>
              <input
                className={`${inputCls} flex-1 min-w-0 py-1 text-xs`}
                type="search"
                placeholder="Search…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  if (!e.target.value) setSearchResults(null);
                }}
              />
              <button type="submit" className={`${btnCls} bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 py-1 text-xs`}>
                Search
              </button>
            </form>

            <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 cursor-pointer whitespace-nowrap">
              <input
                type="checkbox"
                checked={translateEnabled}
                onChange={(e) => setTranslateEnabled(e.target.checked)}
                className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
              />
              Translate
            </label>
            {translateEnabled && (
              <select
                className={`${inputCls} text-xs py-1`}
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
              >
                {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
              </select>
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

      {/* Search info banner */}
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
            <div className="flex items-center justify-center py-12 text-gray-400 dark:text-gray-500 text-sm">
              Loading…
            </div>
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
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <SummaryContent text={summary} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Summarize confirmation modal */}
      {showSummarizeModal && (
        <SummarizeModal
          filename={filename}
          lineCount={lines.length}
          onClose={() => setShowSummarizeModal(false)}
          onDone={handleSummaryDone}
        />
      )}
    </div>
  );
}

function SummaryContent({ text }) {
  const sections = text.split(/\n(?=## )/);
  return (
    <div className="space-y-5">
      {sections.map((section, i) => {
        const lines = section.split("\n");
        const heading = lines[0].startsWith("## ") ? lines[0].slice(3) : null;
        const body = heading ? lines.slice(1).join("\n").trim() : section.trim();
        return (
          <div key={i} className="rounded-lg border border-gray-100 dark:border-gray-700 overflow-hidden">
            {heading && (
              <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700">
                <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">{heading}</h3>
              </div>
            )}
            <div className="px-4 py-3">
              <SummaryBody text={body} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SummaryBody({ text }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (!line.trim()) return null;
        const isBullet = line.trimStart().startsWith("- ") || line.trimStart().startsWith("• ");
        if (isBullet) {
          return (
            <div key={i} className="flex gap-2 text-sm text-gray-700 dark:text-gray-300">
              <span className="text-gray-400 shrink-0 mt-0.5">•</span>
              <span>{line.replace(/^[\s\-•]+/, "")}</span>
            </div>
          );
        }
        return (
          <p key={i} className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{line}</p>
        );
      })}
    </div>
  );
}
