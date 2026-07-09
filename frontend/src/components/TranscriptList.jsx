import { useState, useEffect, useCallback } from "react";
import styles from "./TranscriptList.module.css";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
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
    } catch {
      // ignore
    }
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
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <span className={styles.title}>Transcripts</span>
        <button className={styles.refresh} onClick={load} title="Refresh">↻</button>
      </div>
      <input
        className={styles.search}
        type="search"
        placeholder="Filter…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <ul className={styles.list}>
        {filtered.map((f) => {
          const isActive = selected === f.name;
          const isLive = liveFile === f.name;
          return (
            <li
              key={f.name}
              className={`${styles.item} ${isActive ? styles.active : ""} ${isLive ? styles.live : ""}`}
              onClick={() => onSelect(f.name)}
            >
              <div className={styles.itemName}>{f.name.replace(/\.txt$/, "")}</div>
              <div className={styles.itemMeta}>
                <span>{formatDate(f.modified_iso)}</span>
                <span>{f.line_count} lines · {formatSize(f.size_bytes)}</span>
              </div>
              {isLive && <span className={styles.liveBadge}>LIVE</span>}
              <button
                className={styles.deleteBtn}
                onClick={(e) => handleDelete(e, f.name)}
                disabled={deleting === f.name}
                title="Delete"
              >
                🗑
              </button>
            </li>
          );
        })}
        {filtered.length === 0 && (
          <li className={styles.empty}>No transcripts found</li>
        )}
      </ul>
    </aside>
  );
}
