import { ApiError } from '../../api/client.js';
import * as api from './api.js';
import * as view from './view.js';

const state = {
    unlocked: false,
    playlists: [],
    query: '',
    pending: null, // { playlistId, body } retried after unlock
    noteTimers: {},
};

export function init() {
    view.bind({
        onUnlock: unlock,
        onRate: rate,
        onNote: scheduleNote,
        onSearch: (q) => { state.query = q; paint(); },
    });
    refresh();
}

async function refresh() {
    view.setListState('loading');
    view.setSearchVisible(false);
    try {
        const status = await api.unlockStatus();
        state.unlocked = Boolean(status.unlocked);
    } catch {
        state.unlocked = false;
    }

    try {
        const data = await api.fetchPlaylists();
        // API already ORDER BY pushed_at DESC; keep that order client-side.
        state.playlists = newestFirst(data.playlists || []);
        paint();
        if (!state.playlists.length) return;
        if (!state.unlocked) view.showUnlock();
        else view.hideUnlock();
    } catch (error) {
        view.setSearchVisible(false);
        view.setListState('error', error.message || 'Could not load playlists.');
    }
}

function paint() {
    const all = state.playlists;
    if (!all.length) {
        view.setSearchVisible(false);
        view.setListState('empty');
        return;
    }
    view.setSearchVisible(true);
    const shown = filterPlaylists(all, state.query);
    view.setSearchCount(shown.length, all.length);
    if (!shown.length) {
        view.setListState('empty', 'No playlists match that search.');
        return;
    }
    view.setListState('success');
    view.renderList(shown, { unlocked: state.unlocked });
}

function newestFirst(items) {
    return [...items].sort((a, b) => String(b.pushed_at || '').localeCompare(String(a.pushed_at || '')));
}

function filterPlaylists(items, query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) return items;
    return items.filter((pl) => haystack(pl).includes(q));
}

function haystack(pl) {
    const parts = [pl.name, pl.description];
    for (const t of pl.tracks || []) {
        parts.push(t.track_name, t.artist_name);
    }
    return parts.filter(Boolean).join(' ').toLowerCase();
}

async function unlock(event) {
    event.preventDefault();
    const token = view.unlockInputValue();
    if (!token) {
        view.showUnlock('Enter the password.');
        return;
    }
    view.setUnlockBusy(true);
    try {
        await api.unlock(token);
        state.unlocked = true;
        view.hideUnlock();
        paint();
        if (state.pending) {
            const pending = state.pending;
            state.pending = null;
            await postFeedback(pending.playlistId, pending.body);
        }
    } catch (error) {
        state.unlocked = false;
        view.showUnlock(error.message || 'Wrong password.');
    } finally {
        view.setUnlockBusy(false);
    }
}

async function rate(playlistId, criterion, score) {
    await postFeedback(playlistId, { criterion, score });
}

function scheduleNote(playlistId, note) {
    clearTimeout(state.noteTimers[playlistId]);
    state.noteTimers[playlistId] = setTimeout(() => {
        saveNote(playlistId, note);
    }, 500);
}

async function saveNote(playlistId, note) {
    const pl = state.playlists.find((p) => p.id === playlistId);
    const scores = {};
    for (const f of (pl && pl.feedback) || []) {
        scores[f.criterion] = f.score;
    }
    // API requires at least one score; keep current overall or seed 0.
    if (!Object.keys(scores).length) scores.overall = 0;
    await postFeedback(playlistId, { scores, note });
}

async function postFeedback(playlistId, body) {
    if (!state.unlocked) {
        state.pending = { playlistId, body };
        view.showUnlock('Unlock to save ratings.');
        return;
    }
    try {
        const data = await api.saveFeedback(playlistId, body);
        const pl = state.playlists.find((p) => p.id === playlistId);
        if (pl) pl.feedback = data.feedback || [];
        view.updateCardFeedback(playlistId, data.feedback || []);
    } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
            state.unlocked = false;
            state.pending = { playlistId, body };
            view.showUnlock('Session expired — unlock again.');
            paint();
            return;
        }
        view.showUnlock(error.message || 'Could not save rating.');
    }
}
