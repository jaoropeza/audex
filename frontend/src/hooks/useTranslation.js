import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Batches incoming lines and translates them via POST /api/translate.
 * Lines are debounced by 300 ms then sent in a single request.
 *
 * @param {string[]} lines      Raw transcript lines to translate
 * @param {string}  targetLang  e.g. "English", "Spanish"
 * @param {boolean} enabled
 * @returns {{ translations: Object, translating: boolean, error: string|null }}
 *   translations: { [lineText]: translatedText }
 */
export function useTranslation(lines, targetLang, enabled) {
  const [translations, setTranslations] = useState({});
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState(null);
  const pendingRef = useRef([]);
  const timerRef = useRef(null);
  const translatedKeys = useRef(new Set());

  const flush = useCallback(async () => {
    const batch = pendingRef.current.filter((l) => !translatedKeys.current.has(l));
    pendingRef.current = [];
    if (!batch.length) return;

    setTranslating(true);
    setError(null);
    try {
      const res = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lines: batch, target_language: targetLang }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Translation failed");
      const { translations: translated } = await res.json();
      const map = {};
      batch.forEach((orig, i) => {
        map[orig] = translated[i] ?? orig;
        translatedKeys.current.add(orig);
      });
      setTranslations((prev) => ({ ...prev, ...map }));
    } catch (err) {
      setError(err.message);
    } finally {
      setTranslating(false);
    }
  }, [targetLang]);

  useEffect(() => {
    if (!enabled || !lines.length) return;

    // Queue untranslated lines
    const newLines = lines.filter((l) => !translatedKeys.current.has(l));
    if (!newLines.length) return;

    pendingRef.current.push(...newLines);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(flush, 300);

    return () => clearTimeout(timerRef.current);
  }, [lines, enabled, flush]);

  // Reset when target language changes
  useEffect(() => {
    translatedKeys.current.clear();
    setTranslations({});
  }, [targetLang]);

  return { translations, translating, error };
}
