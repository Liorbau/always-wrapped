// DOM for the chat panel. Receives callbacks; never fetches, never polls.

import { byId, esc } from '../../shared/dom.js';
import { BUBBLE_ICON, TRANSCRIPT_KEY } from './constants.js';

export function mountPanel({
    onSend, onStop, onClear, onToggle, onUnlock, onPlantimeSave, onPlantimeOff, onHelp,
}) {
    const root = byId('aw-chat-root');
    if (!root) return false;

    root.innerHTML = `
        <button id="aw-chat-bubble" title="Ask the DJ">${BUBBLE_ICON}</button>
        <div id="aw-chat-panel" class="aw-hidden">
            <div class="aw-chat-header">
                <span class="aw-chat-title">AI Wrapped<span class="green-dot">.</span></span>
                <button class="aw-chat-help" title="Commands" type="button">?</button>
                <button class="aw-chat-clear" title="Clear conversation"><i class="fas fa-trash-can"></i></button>
                <button class="aw-chat-close" title="Close">&times;</button>
            </div>
            <div id="aw-commands" class="aw-hidden"></div>
            <div id="aw-plantime" class="aw-hidden">
                <label for="aw-plantime-input">Nightly planner</label>
                <input id="aw-plantime-input" type="time" />
                <button type="button" id="aw-plantime-save" title="Save time">Save</button>
                <button type="button" id="aw-plantime-off" title="Turn off">Off</button>
            </div>
            <div id="aw-unlock" class="aw-hidden">
                <p class="aw-unlock-copy">Enter the owner password to use the DJ and push playlists.</p>
                <form id="aw-unlock-form">
                    <input id="aw-unlock-input" type="password" autocomplete="current-password"
                           placeholder="Password" />
                    <button type="submit">Unlock</button>
                </form>
                <p id="aw-unlock-error" class="aw-unlock-error aw-hidden"></p>
            </div>
            <div id="aw-chat-messages"></div>
            <form id="aw-chat-form">
                <input id="aw-chat-input" autocomplete="off"
                       placeholder="Ask for a playlist, or /help" />
                <button type="button" id="aw-stop" class="aw-hidden" title="Stop the DJ">
                    <i class="fas fa-stop"></i></button>
                <button type="submit" id="aw-send"><i class="fas fa-paper-plane"></i></button>
            </form>
        </div>`;

    byId('aw-chat-bubble').addEventListener('click', onToggle);
    root.querySelector('.aw-chat-close').addEventListener('click', onToggle);
    root.querySelector('.aw-chat-clear').addEventListener('click', onClear);
    root.querySelector('.aw-chat-help').addEventListener('click', onHelp);
    byId('aw-chat-form').addEventListener('submit', onSend);
    byId('aw-stop').addEventListener('click', onStop);
    byId('aw-unlock-form').addEventListener('submit', onUnlock);
    byId('aw-plantime-save').addEventListener('click', onPlantimeSave);
    byId('aw-plantime-off').addEventListener('click', onPlantimeOff);
    return true;
}

export function commandsPanelIsOpen() {
    return !byId('aw-commands').classList.contains('aw-hidden');
}

export function hideCommandsPanel() {
    byId('aw-commands').classList.add('aw-hidden');
    byId('aw-commands').innerHTML = '';
}

export function renderCommandsPanel(payload) {
    const panel = byId('aw-commands');
    const commands = (payload && payload.commands) || [];
    const rows = commands.map((c) =>
        `<div class="aw-cmd"><code>${esc(c.usage)}</code>` +
        `<span>${esc(c.blurb)}</span></div>`).join('');
    panel.innerHTML = `
        <div class="aw-commands-head">Commands</div>
        <div class="aw-commands-list">${rows}</div>
        <p class="aw-commands-note">Or type <code>/help</code>. Plain language works too.</p>`;
    panel.classList.remove('aw-hidden');
}

export function panelIsOpen() {
    return !byId('aw-chat-panel').classList.contains('aw-hidden');
}

export function showUnlockGate(errorMessage) {
    byId('aw-unlock').classList.remove('aw-hidden');
    byId('aw-plantime').classList.add('aw-hidden');
    byId('aw-chat-messages').classList.add('aw-hidden');
    byId('aw-chat-form').classList.add('aw-hidden');
    const err = byId('aw-unlock-error');
    if (errorMessage) {
        err.textContent = errorMessage;
        err.classList.remove('aw-hidden');
    } else {
        err.textContent = '';
        err.classList.add('aw-hidden');
    }
    byId('aw-unlock-input').focus();
}

export function hideUnlockGate() {
    byId('aw-unlock').classList.add('aw-hidden');
    byId('aw-plantime').classList.remove('aw-hidden');
    byId('aw-chat-messages').classList.remove('aw-hidden');
    byId('aw-chat-form').classList.remove('aw-hidden');
    byId('aw-unlock-error').classList.add('aw-hidden');
    byId('aw-unlock-input').value = '';
}

export function renderPlantime(schedule) {
    const input = byId('aw-plantime-input');
    if (!input) return;
    input.value = schedule && schedule.enabled && schedule.at ? schedule.at : '';
}

export function plantimeInputValue() {
    return byId('aw-plantime-input').value;
}

export function setPlantimeBusy(busy) {
    byId('aw-plantime-save').disabled = busy;
    byId('aw-plantime-off').disabled = busy;
    byId('aw-plantime-input').disabled = busy;
}

export function unlockInputValue() {
    return byId('aw-unlock-input').value;
}

export function setUnlockBusy(busy) {
    const form = byId('aw-unlock-form');
    form.querySelector('button').disabled = busy;
    byId('aw-unlock-input').disabled = busy;
}

export function togglePanel() {
    const panel = byId('aw-chat-panel');
    panel.classList.toggle('aw-hidden');
    if (!panel.classList.contains('aw-hidden')) scrollToLatest();
}

export function setBusy(busy) {
    byId('aw-send').disabled = busy;
    byId('aw-stop').classList.toggle('aw-hidden', !busy);
}

export function addMessage(who, html) {
    const messages = byId('aw-chat-messages');
    const bubble = document.createElement('div');
    bubble.className = `aw-msg aw-${who}`;
    bubble.innerHTML = html;
    messages.appendChild(bubble);
    scrollToLatest();
    saveTranscript();
    return bubble;
}

export function addStatusLine() {
    return addMessage('status',
        '<i class="fas fa-circle-notch fa-spin"></i> <span class="aw-status-text">thinking…</span>');
}

export function updateStatus(statusEl, agent, activity) {
    const textEl = statusEl.querySelector('.aw-status-text');
    const label = `${agent} · ${activity}`;
    if (!textEl || textEl.dataset.label === label) return;
    // swap only the text so the spinner element persists and its rotation
    // never restarts mid-run
    textEl.dataset.label = label;
    textEl.innerHTML = `<strong>${esc(agent)}</strong> · ${esc(activity)}…`;
}

export function renderResult(result) {
    if (result.type === 'playlist_proposal') {
        addMessage('agent', esc(result.response));
        return { proposalId: result.proposal_id, playlist: result.playlist };
    }
    addMessage('agent', esc(result.response) + (result.withheld
        ? '<div class="aw-withheld">proposal withheld — constraints not met</div>'
        : ''));
    return null;
}

export function renderProposal(proposalId, playlist, { onApprove, onReject }) {
    const tracks = (playlist.tracks || []).map((track) => `
        <div class="aw-track">
            <span class="aw-fam aw-fam-${esc(track.familiarity)}">${esc(track.familiarity || '?')}</span>
            <span class="aw-track-name" title="${esc(track.reason)}">${esc(track.track_name)}
                <em>— ${esc(track.artist_name)}</em></span>
        </div>`).join('');

    const capNote = (playlist.artist_cap > 2 && playlist.artist_cap_reason)
        ? `<div class="aw-card-cap">Up to ${esc(playlist.artist_cap)} per artist — ${esc(playlist.artist_cap_reason)}</div>`
        : '';

    const card = addMessage('card', `
        <div class="aw-card-head">
            <strong>${esc(playlist.name)}</strong>
            <span class="aw-duration">${esc(Math.round(playlist.total_duration_min || 0))} min</span>
        </div>
        <div class="aw-card-desc">${esc(playlist.description)}</div>
        ${capNote}
        <div class="aw-tracks">${tracks}</div>
        <div class="aw-card-actions">
            <button class="aw-approve"><i class="fas fa-check"></i> Approve &amp; push</button>
            <button class="aw-reject"><i class="fas fa-times"></i> Reject</button>
        </div>
        <div class="aw-reject-box aw-hidden">
            <input placeholder="why? (optional — the DJ learns from this)" maxlength="200">
            <button class="aw-reject-send">Send</button>
        </div>`);

    card.querySelector('.aw-approve').onclick = () => onApprove(proposalId, card);
    card.querySelector('.aw-reject').onclick = () =>
        card.querySelector('.aw-reject-box').classList.remove('aw-hidden');
    card.querySelector('.aw-reject-send').onclick = () => onReject(proposalId, card);
    saveTranscript();
    return card;
}

export function rejectionReason(card) {
    return card.querySelector('.aw-reject-box input').value.trim();
}

export function setCardBusy(card, busy) {
    card.querySelectorAll('button').forEach((button) => { button.disabled = busy; });
}

export function markPushed(card, url) {
    card.querySelector('.aw-card-actions').innerHTML =
        `<a class="aw-pushed" href="${esc(url)}" target="_blank" rel="noopener">
            <i class="fab fa-spotify"></i> Pushed — open in Spotify</a>`;
    saveTranscript();
}

export function markRejected(card) {
    card.querySelector('.aw-card-actions').innerHTML =
        '<span class="aw-rejected">rejected — the DJ will learn from it</span>';
    card.querySelector('.aw-reject-box').classList.add('aw-hidden');
    saveTranscript();
}

export function clearMessages() {
    byId('aw-chat-messages').innerHTML = '';
    localStorage.removeItem(TRANSCRIPT_KEY);
}

export function scrollToLatest() {
    const messages = byId('aw-chat-messages');
    messages.scrollTop = messages.scrollHeight;
}

// Transcript persistence is visual only — the agent's memory lives server-side.
export function saveTranscript() {
    const clone = byId('aw-chat-messages').cloneNode(true);
    clone.querySelectorAll('.aw-status').forEach((el) => el.remove());  // never persist spinners
    localStorage.setItem(TRANSCRIPT_KEY, clone.innerHTML);
}

export function restoreTranscript() {
    const saved = localStorage.getItem(TRANSCRIPT_KEY);
    if (!saved) return;
    const messages = byId('aw-chat-messages');
    messages.innerHTML = saved;
    // proposal buttons don't survive a restart — their handlers are gone
    messages.querySelectorAll('.aw-card-actions button').forEach((b) => { b.disabled = true; });
    scrollToLatest();
}
