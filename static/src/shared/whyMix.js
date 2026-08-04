// Compact “Why this mix” block from a decision_trace (facts, not CoT).

import { esc } from './dom.js';

export function whyMixHtml(trace) {
    if (!trace || !Array.isArray(trace.summary) || !trace.summary.length) return '';
    const lines = trace.summary.map((line) => `<li>${esc(line)}</li>`).join('');
    const note = trace.model_vs_facts
        ? `<p class="aw-why-note">${esc(trace.model_vs_facts)}</p>`
        : '';
    return `
    <details class="aw-why">
        <summary>Why this mix</summary>
        <ul class="aw-why-summary">${lines}</ul>
        ${note}
    </details>`;
}

/** Shelf API nests the trace under context.decision_trace. */
export function traceFromPlaylist(playlist) {
    if (!playlist) return null;
    return playlist.decision_trace
        || (playlist.context && playlist.context.decision_trace)
        || null;
}
