export function parseLine(raw) {
  const bracketRe = /\[([^\]]+)\]/g;
  const parts = { timestamp: null, label: null, speaker: null, text: raw };
  const matches = [...raw.matchAll(bracketRe)];
  const timeRe = /^\d{2}:\d{2}:\d{2}$/;

  if (matches.length > 0) {
    let idx = 0;
    for (const m of matches) {
      if (idx === 0 && timeRe.test(m[1])) { parts.timestamp = m[1]; idx++; }
      else if (idx <= 1 && (m[1] === "MIC" || m[1] === "SPK")) { parts.label = m[1]; idx++; }
      else if (idx <= 2 && !/^\d{2}:\d{2}:\d{2}$/.test(m[1])) { parts.speaker = m[1]; idx++; }
    }
    const lastBracketEnd = raw.lastIndexOf("]");
    parts.text = raw.slice(lastBracketEnd + 1).trim();
  }

  return parts;
}

export default function TranscriptLine({ raw, translation, searchTerm }) {
  const { timestamp, label, speaker, text } = parseLine(raw);

  function highlight(str) {
    if (!searchTerm) return str;
    const idx = str.toLowerCase().indexOf(searchTerm.toLowerCase());
    if (idx === -1) return str;
    return (
      <>
        {str.slice(0, idx)}
        <mark className="bg-yellow-200 dark:bg-yellow-800/60 text-yellow-900 dark:text-yellow-200 rounded-sm px-0.5">
          {str.slice(idx, idx + searchTerm.length)}
        </mark>
        {str.slice(idx + searchTerm.length)}
      </>
    );
  }

  return (
    <div className="flex flex-col py-1.5 px-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 border-b border-gray-100 dark:border-gray-800/50 transition-colors">
      <div className="flex items-start gap-2 flex-wrap">
        {/* Meta badges */}
        <span className="flex items-center gap-1 shrink-0 pt-0.5">
          {timestamp && (
            <span className="font-mono text-[11px] text-gray-400 dark:text-gray-500 tabular-nums">
              {timestamp}
            </span>
          )}
          {label === "MIC" && (
            <span className="inline-flex items-center rounded px-1 py-0.5 text-[9px] font-bold bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 leading-none">
              MIC
            </span>
          )}
          {label === "SPK" && (
            <span className="inline-flex items-center rounded px-1 py-0.5 text-[9px] font-bold bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 leading-none">
              SPK
            </span>
          )}
          {speaker && (
            <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 leading-none">
              {speaker}
            </span>
          )}
        </span>

        {/* Text */}
        <span className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed flex-1">
          {highlight(text)}
        </span>
      </div>

      {/* Translation */}
      {translation && translation !== raw && (
        <div className="mt-1 ml-0 pl-3 border-l-2 border-blue-300 dark:border-blue-600 text-sm text-blue-700 dark:text-blue-300 italic">
          {translation}
        </div>
      )}
    </div>
  );
}
