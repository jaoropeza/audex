import { useState, useEffect } from "react";
import TranscriptLine from "./TranscriptLine";
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

  const { translations } = useTranslation(lines, targetLang, translateEnabled);

  useEffect(() => {
    if (!filename) return;
    setLoading(true);
    setLines([]);
    setSearchResults(null);
    fetch(`/api/transcripts/${encodeURIComponent(filename)}`)
      .then((r) => r.json())
      .then(({ lines: l }) => { setLines(l); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filename]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!search.trim()) { setSearchResults(null); return; }
    const res = await fetch(
      `/api/transcripts/${encodeURIComponent(filename)}/search?q=${encodeURIComponent(search)}`
    );
    const { matches } = await res.json();
    setSearchResults(matches);
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
      </div>

      {/* Search info banner */}
      {searchResults && (
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

      {/* Content */}
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
    </div>
  );
}
