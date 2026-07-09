import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Connects an EventSource to `url` and accumulates incoming "line" events.
 * @param {string|null} url  Full path, e.g. "/api/stream/meeting_20260708.txt"
 * @param {boolean} enabled  Only connect when true
 * @returns {{ lines: string[], status: string, clear: Function }}
 *   status: "idle" | "connecting" | "open" | "eof" | "error"
 */
export function useSSE(url, enabled = true) {
  const [lines, setLines] = useState([]);
  const [status, setStatus] = useState("idle");
  const esRef = useRef(null);
  const lastLineRef = useRef(0);

  const clear = useCallback(() => {
    setLines([]);
    lastLineRef.current = 0;
  }, []);

  useEffect(() => {
    if (!url || !enabled) {
      setStatus("idle");
      return;
    }

    const fromLine = lastLineRef.current;
    const fullUrl = fromLine > 0 ? `${url}?from_line=${fromLine}` : url;

    setStatus("connecting");
    const es = new EventSource(fullUrl);
    esRef.current = es;

    es.addEventListener("line", (e) => {
      const { text, line_number } = JSON.parse(e.data);
      lastLineRef.current = line_number;
      setLines((prev) => [...prev, text]);
    });

    es.addEventListener("eof", () => {
      setStatus("eof");
      es.close();
    });

    es.addEventListener("error", () => {
      // EventSource auto-reconnects on transient errors; only set error on
      // CLOSED state (permanent failure after retries)
      if (es.readyState === EventSource.CLOSED) {
        setStatus("error");
      }
    });

    es.onopen = () => setStatus("open");

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [url, enabled]);

  return { lines, status, clear };
}
