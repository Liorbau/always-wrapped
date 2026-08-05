import { byId, esc } from '../../shared/dom.js';
import { whyMixHtml, traceFromPlaylist } from '../../shared/whyMix.js';
import { CRITERIA } from './constants.js';

export function bind({ onUnlock, onRate, onNote, onSearch }) {
    byId('pl-unlock-form').addEventListener('submit', onUnlock);
    byId('pl-search').addEventListener('input', (event) => onSearch(event.target.value));
    byId('pl-list').addEventListener('click', (event) => {
        const star = event.target.closest('[data-star]');
        if (!star) return;
        onRate(star.dataset.playlistId, star.dataset.criterion, Number(star.dataset.star));
    });
    byId('pl-list').addEventListener('change', (event) => {
        const note = event.target.closest('[data-note]');
        if (!note) return;
        onNote(note.dataset.playlistId, note.value);
    });
}

export function setSearchVisible(visible) {
    byId('pl-search-wrap').classList.toggle('aw-hidden', !visible);
}

export function setSearchCount(shown, total) {
    const el = byId('pl-search-count');
    if (!total) {
        el.textContent = '';
        return;
    }
    el.textContent = shown === total ? `${total}` : `${shown} / ${total}`;
}

export function setListState(kind, message) {
    const status = byId('pl-status');
    const list = byId('pl-list');
    if (kind === 'loading') {
        status.textContent = message || 'Loading…';
        status.classList.remove('aw-hidden');
        list.innerHTML = '';
        return;
    }
    if (kind === 'empty') {
        status.textContent = message || 'No DJ playlists yet — approve one from chat.';
        status.classList.remove('aw-hidden');
        list.innerHTML = '';
        return;
    }
    if (kind === 'error') {
        status.textContent = message || 'Could not load playlists.';
        status.classList.remove('aw-hidden');
        list.innerHTML = '';
        return;
    }
    status.classList.add('aw-hidden');
}

export function renderList(playlists, { unlocked }) {
    const list = byId('pl-list');
    list.innerHTML = playlists.map((pl) => cardHtml(pl, unlocked)).join('');
}

export function showUnlock(errorMessage) {
    byId('pl-unlock').classList.remove('aw-hidden');
    const err = byId('pl-unlock-error');
    if (errorMessage) {
        err.textContent = errorMessage;
        err.classList.remove('aw-hidden');
    } else {
        err.textContent = '';
        err.classList.add('aw-hidden');
    }
    byId('pl-unlock-input').focus();
}

export function hideUnlock() {
    byId('pl-unlock').classList.add('aw-hidden');
    byId('pl-unlock-error').classList.add('aw-hidden');
    byId('pl-unlock-input').value = '';
}

export function unlockInputValue() {
    return byId('pl-unlock-input').value;
}

export function setUnlockBusy(busy) {
    byId('pl-unlock-input').disabled = busy;
    byId('pl-unlock-form').querySelector('button').disabled = busy;
}

export function updateCardFeedback(playlistId, feedback) {
    const card = byId(`pl-card-${playlistId}`);
    if (!card) return;
    const byCrit = Object.fromEntries((feedback || []).map((f) => [f.criterion, f]));
    for (const { id } of CRITERIA) {
        const score = byCrit[id] ? Number(byCrit[id].score) : 0;
        card.querySelectorAll(`[data-criterion="${id}"][data-star]`).forEach((btn) => {
            const n = Number(btn.dataset.star);
            btn.classList.toggle('on', n <= score && score > 0);
            btn.setAttribute('aria-pressed', n === score ? 'true' : 'false');
        });
    }
    const note = (feedback || []).find((f) => f.note)?.note || '';
    const noteEl = card.querySelector('[data-note]');
    if (noteEl && document.activeElement !== noteEl) noteEl.value = note;
}

function cardHtml(pl, unlocked) {
    const when = formatWhen(pl.pushed_at);
    const byCrit = Object.fromEntries((pl.feedback || []).map((f) => [f.criterion, f]));
    const note = (pl.feedback || []).find((f) => f.note)?.note || '';
    const tracks = (pl.tracks || []).slice(0, 5);
    const more = Math.max(0, (pl.tracks || []).length - tracks.length);
    const why = whyMixHtml(traceFromPlaylist(pl));
    const outcome = outcomeLine(pl.outcome);

    return `
    <article class="pl-card" id="pl-card-${esc(pl.id)}" data-id="${esc(pl.id)}">
        <div class="pl-card-head">
            <div>
                <h2>${esc(pl.name || 'Untitled')}</h2>
                <p class="pl-meta">${esc(when)}${pl.description ? ` · ${esc(pl.description)}` : ''}</p>
                ${outcome}
            </div>
            ${pl.url ? `<a class="pl-spotify" href="${esc(pl.url)}" target="_blank" rel="noopener">Open in Spotify</a>` : ''}
        </div>
        ${why}
        <ul class="pl-tracks">
            ${tracks.map((t) => `
                <li>${esc(t.track_name || '?')}
                    <em>— ${esc(t.artist_name || '')}</em></li>`).join('')}
            ${more ? `<li class="pl-more">+${more} more</li>` : ''}
        </ul>
        <div class="pl-ratings ${unlocked ? '' : 'pl-ratings-locked'}">
            ${CRITERIA.map(({ id, label, hint }) => starsRow(pl.id, id, label, byCrit[id], hint)).join('')}
            <label class="pl-note">
                <span>Note</span>
                <textarea data-note data-playlist-id="${esc(pl.id)}" rows="2"
                    placeholder="${unlocked ? 'Optional note…' : 'Unlock to rate'}"
                    ${unlocked ? '' : 'disabled'}>${esc(note)}</textarea>
            </label>
        </div>
    </article>`;
}

function starsRow(playlistId, criterion, label, feedback, hint) {
    const score = feedback ? Number(feedback.score) : 0;
    const stars = [1, 2, 3, 4, 5].map((n) => `
        <button type="button" class="pl-star ${n <= score && score > 0 ? 'on' : ''}"
            data-star="${n}" data-criterion="${esc(criterion)}"
            data-playlist-id="${esc(playlistId)}"
            aria-label="${esc(label)} ${n} of 5"
            aria-pressed="${n === score ? 'true' : 'false'}">★</button>`).join('');
    const title = hint ? ` title="${esc(hint)}"` : '';
    return `
    <div class="pl-crit">
        <span class="pl-crit-label"${title}>${esc(label)}</span>
        <div class="pl-stars" role="group" aria-label="${esc(label)}">${stars}</div>
    </div>`;
}

function formatWhen(iso) {
    if (!iso) return '';
    const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T'));
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function outcomeLine(outcome) {
    if (!outcome) return '';
    if (outcome.status === 'never_played') {
        return '<p class="pl-outcome">No plays after push</p>';
    }
    const bits = [];
    if (outcome.skip_rate != null) bits.push(`skip ${Math.round(outcome.skip_rate * 100)}%`);
    if (outcome.completion_rate != null) {
        bits.push(`complete ${Math.round(outcome.completion_rate * 100)}%`);
    }
    if (outcome.mean_rating != null) bits.push(`★ ${outcome.mean_rating}`);
    if (!bits.length) return '';
    return `<p class="pl-outcome" title="${esc(outcome.note || '')}">${esc(bits.join(' · '))}</p>`;
}
