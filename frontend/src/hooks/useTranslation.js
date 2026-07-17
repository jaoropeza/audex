import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { parseLine } from "../components/TranscriptLine";
import { apiFetch } from "../utils/api";

// ── helpers ───────────────────────────────────────────────────────────────────

function parseTimestampSec(raw) {
  const m = raw.match(/^\[(\d{2}):(\d{2}):(\d{2})\]/);
  if (!m) return null;
  return +m[1] * 3600 + +m[2] * 60 + +m[3];
}

/**
 * Split lines into time-based groups.
 * groupSeconds = null/0 → each line is its own group (per-line mode).
 * groupSeconds > 0     → consecutive lines within a window form one group.
 *
 * Returns: Array<{ key: string, lines: string[] }>
 */
export function buildGroups(lines, groupSeconds) {
  if (!groupSeconds) {
    return lines.map((line, i) => ({ key: `line_${i}`, lines: [line] }));
  }

  const groups = [];
  let current = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const sec = parseTimestampSec(line);

    if (!current) {
      current = { key: `g${i}`, lines: [line], startSec: sec };
    } else if (sec === null || current.startSec === null || sec - current.startSec < groupSeconds) {
      current.lines.push(line);
    } else {
      groups.push(current);
      current = { key: `g${i}`, lines: [line], startSec: sec };
    }
  }
  if (current) groups.push(current);
  return groups;
}

// ── hook ──────────────────────────────────────────────────────────────────────

async function callApi(texts, sourceLang, targetLang, promptTemplate) {
  const res = await apiFetch("/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lines: texts,
      source_language: sourceLang || "auto",
      target_language: targetLang,
      prompt_template: promptTemplate || null,
    }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Translation failed");
  const { translations } = await res.json();
  return translations;
}

/**
 * @param {string[]}     lines          Raw transcript lines
 * @param {string}       sourceLang     e.g. "Auto", "Spanish"
 * @param {string}       targetLang     e.g. "English"
 * @param {string|null}  promptTemplate Custom prompt or null for default
 * @param {number|null}  groupSeconds   null = per-line, >0 = group window size
 * @param {boolean}      enabled
 */
export function useTranslation(lines, sourceLang, targetLang, promptTemplate, groupSeconds, enabled) {
  const [translations, setTranslations] = useState({});
  const [translating, setTranslating]   = useState(false);
  const [error, setError]               = useState(null);

  const doneKeys    = useRef(new Set());
  const pendingRef  = useRef([]);
  const timerRef    = useRef(null);
  const cancelRef   = useRef(false);

  // Compute groups (per-line when groupSeconds is falsy)
  const groups = useMemo(() => buildGroups(lines, groupSeconds), [lines, groupSeconds]);

  // Reset everything when translation settings change
  useEffect(() => {
    cancelRef.current = true;   // abort any in-flight group loop
    doneKeys.current.clear();
    pendingRef.current = [];
    clearTimeout(timerRef.current);
    setTranslations({});
    setError(null);
    setTranslating(false);
    // Let the next render start fresh
    cancelRef.current = false;
  }, [sourceLang, targetLang, promptTemplate, groupSeconds]);

  // ── PER-LINE MODE (groupSeconds falsy) ──────────────────────────────────────
  const flushPerLine = useCallback(async () => {
    const batch = pendingRef.current.filter((l) => !doneKeys.current.has(l));
    pendingRef.current = [];
    if (!batch.length) return;

    setTranslating(true);
    setError(null);
    try {
      const contents = batch.map((raw) => parseLine(raw).text);
      const translated = await callApi(contents, sourceLang, targetLang, promptTemplate);
      const map = {};
      batch.forEach((raw, i) => {
        map[raw] = translated[i] ?? parseLine(raw).text;
        doneKeys.current.add(raw);
      });
      setTranslations((prev) => ({ ...prev, ...map }));
    } catch (err) {
      setError(err.message);
    } finally {
      setTranslating(false);
    }
  }, [sourceLang, targetLang, promptTemplate]);

  useEffect(() => {
    if (groupSeconds || !enabled || !lines.length) return;
    const newLines = lines.filter((l) => !doneKeys.current.has(l));
    if (!newLines.length) return;
    pendingRef.current.push(...newLines);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(flushPerLine, 300);
    return () => clearTimeout(timerRef.current);
  }, [lines, enabled, groupSeconds, flushPerLine]);

  // ── GROUPED MODE (groupSeconds > 0) ─────────────────────────────────────────
  useEffect(() => {
    if (!groupSeconds || !enabled || !groups.length) return;
    const newGroups = groups.filter((g) => !doneKeys.current.has(g.key));
    if (!newGroups.length) return;

    cancelRef.current = false;
    setTranslating(true);
    setError(null);

    (async () => {
      for (const group of newGroups) {
        if (cancelRef.current || doneKeys.current.has(group.key)) continue;

        const joined = group.lines.map((raw) => parseLine(raw).text).join(" ");
        try {
          const [translated] = await callApi([joined], sourceLang, targetLang, promptTemplate);
          if (cancelRef.current) break;
          doneKeys.current.add(group.key);
          setTranslations((prev) => ({ ...prev, [group.key]: translated ?? joined }));
        } catch (err) {
          if (!cancelRef.current) setError(err.message);
          break;
        }
      }
      if (!cancelRef.current) setTranslating(false);
    })();

    return () => { cancelRef.current = true; };
  }, [groups, enabled, groupSeconds, sourceLang, targetLang, promptTemplate]);

  return { translations, groups, translating, error };
}
