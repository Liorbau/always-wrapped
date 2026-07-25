export const SESSION_KEY = 'aw_session_id';
export const TRANSCRIPT_KEY = 'aw_chat_transcript';

export const RUN_POLL_MS = 1200;
export const PLAN_POLL_MS = 2000;
export const POLL_TIMEOUT_MS = 5 * 60 * 1000;
export const MAX_CONSECUTIVE_MISSES = 5;

export const AGENT_LABELS = {
    playlist_request: 'DJ',
    data_question: 'Analyst',
};

// AI star nested between the headphone cups
export const BUBBLE_ICON = `
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
        <path d="M4 16.5v-3.3a8 8 0 0 1 16 0v3.3" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"></path>
        <rect x="2.8" y="14.2" width="4.4" height="6.6" rx="2.2" fill="currentColor"></rect>
        <rect x="16.8" y="14.2" width="4.4" height="6.6" rx="2.2" fill="currentColor"></rect>
        <path d="M12 10.6c.5 2.2 1.2 2.9 3.4 3.4-2.2.5-2.9 1.2-3.4 3.4-.5-2.2-1.2-2.9-3.4-3.4 2.2-.5 2.9-1.2 3.4-3.4z" fill="currentColor"></path>
    </svg>`;
