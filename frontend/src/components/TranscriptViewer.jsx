import { useState, useEffect } from "react";
import TranscriptLine from "./TranscriptLine";
import { useTranslation } from "../hooks/useTranslation";
import styles from "./TranscriptViewer.module.css";

const LANGUAGES = ["English", "Spanish", "French", "Portuguese", "German", "Italian", "Japanese", "Chinese"];

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

  const displayLines = searchResults
    ? searchResults.map((m) => m.text)
    : lines;

  if (!filename) {
    return (
      <div className={styles.empty}>
        <p>Select a transcript from the sidebar to view it.</p>
      </div>
    );
  }

  return (
    <div className={styles.viewer}>
      <div className={styles.toolbar}>
        <span className={styles.fname}>{filename}</span>
        <form className={styles.searchForm} onSubmit={handleSearch}>
          <input
            className={styles.searchInput}
            type="search"
            placeholder="Search…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); if (!e.target.value) setSearchResults(null); }}
          />
          <button type="submit" className={styles.searchBtn}>Search</button>
        </form>
        <label className={styles.toggle}>
          <input type="checkbox" checked={translateEnabled} onChange={(e) => setTranslateEnabled(e.target.checked)} />
          Translate
        </label>
        {translateEnabled && (
          <select
            className={styles.langSelect}
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
          >
            {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
          </select>
        )}
      </div>

      {searchResults && (
        <div className={styles.searchInfo}>
          {searchResults.length} match{searchResults.length !== 1 ? "es" : ""} for "{search}"
          <button className={styles.clearSearch} onClick={() => { setSearchResults(null); setSearch(""); }}>
            ✕ Clear
          </button>
        </div>
      )}

      <div className={styles.content}>
        {loading && <p className={styles.hint}>Loading…</p>}
        {!loading && displayLines.length === 0 && (
          <p className={styles.hint}>{searchResults ? "No matches." : "Empty transcript."}</p>
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
