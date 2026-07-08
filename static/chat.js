// Always-Wrapped agent chat: floating bubble -> panel, live step feed,
// proposal cards with HITL Approve/Reject, multi-turn sessions, provider picker.
// v2: bubble icon = AI star between the headphone cups (inline SVG).

const AW = {
    sessionId: localStorage.getItem('aw_session_id') || null,
    busy: false,
    runId: null,
};

function setBusyUI(busy) {
    AW.busy = busy;
    document.getElementById('aw-send').disabled = busy;
    document.getElementById('aw-stop').classList.toggle('aw-hidden', !busy);
}

async function stopRun() {
    if (!AW.runId) return;
    try { await awApi(`/api/agent/run/${AW.runId}/stop`, {}); } catch {}
    // the poll loop sees done and renders the stop message
}

// AI star nested between the headphone cups
const AW_BUBBLE_ICON = `
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
        <path d="M4 16.5v-3.3a8 8 0 0 1 16 0v3.3" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"></path>
        <rect x="2.8" y="14.2" width="4.4" height="6.6" rx="2.2" fill="currentColor"></rect>
        <rect x="16.8" y="14.2" width="4.4" height="6.6" rx="2.2" fill="currentColor"></rect>
        <path d="M12 10.6c.5 2.2 1.2 2.9 3.4 3.4-2.2.5-2.9 1.2-3.4 3.4-.5-2.2-1.2-2.9-3.4-3.4 2.2-.5 2.9-1.2 3.4-3.4z" fill="currentColor"></path>
    </svg>`;

document.addEventListener('DOMContentLoaded', initChat);

function initChat() {
    const root = document.getElementById('aw-chat-root');
    if (!root) return;
    root.innerHTML = `
        <button id="aw-chat-bubble" title="Ask the DJ">${AW_BUBBLE_ICON}</button>
        <div id="aw-chat-panel" class="aw-hidden">
            <div class="aw-chat-header">
                <span class="aw-chat-title">AI Wrapped<span class="green-dot">.</span></span>
                <button class="aw-chat-clear" title="Clear conversation"><i class="fas fa-trash-can"></i></button>
                <button class="aw-chat-close" onclick="toggleChat()">&times;</button>
            </div>
            <div id="aw-chat-messages"></div>
            <form id="aw-chat-form">
                <input id="aw-chat-input" autocomplete="off"
                       placeholder="Ask for a playlist or about your listening" />
                <button type="button" id="aw-stop" class="aw-hidden" title="Stop the DJ">
                    <i class="fas fa-stop"></i></button>
                <button type="submit" id="aw-send"><i class="fas fa-paper-plane"></i></button>
            </form>
        </div>`;

    document.getElementById('aw-chat-bubble').addEventListener('click', toggleChat);
    document.querySelector('.aw-chat-clear').addEventListener('click', clearConversation);
    document.getElementById('aw-chat-form').addEventListener('submit', onSend);
    document.getElementById('aw-stop').addEventListener('click', stopRun);
    restoreTranscript();
}



function clearConversation() {
    if (!confirm('Clear the conversation? The DJ forgets this chat.')) return;
    document.getElementById('aw-chat-messages').innerHTML = '';
    localStorage.removeItem('aw_chat_transcript');
    localStorage.removeItem('aw_session_id');
    AW.sessionId = null;
    setBusyUI(false);  // also unsticks a wedged client
    addMsg('system', '— conversation cleared —');
}

function toggleChat() {
    const panel = document.getElementById('aw-chat-panel');
    panel.classList.toggle('aw-hidden');
    if (!panel.classList.contains('aw-hidden')) {
        const msgs = document.getElementById('aw-chat-messages');
        msgs.scrollTop = msgs.scrollHeight;   // land at the latest message
    }
}

// --- transcript persistence (visual only; agent memory lives server-side) ---
function saveTranscript() {
    const clone = document.getElementById('aw-chat-messages').cloneNode(true);
    clone.querySelectorAll('.aw-status').forEach(el => el.remove());  // never persist spinners
    localStorage.setItem('aw_chat_transcript', clone.innerHTML);
}
function restoreTranscript() {
    const saved = localStorage.getItem('aw_chat_transcript');
    if (saved) {
        const msgs = document.getElementById('aw-chat-messages');
        msgs.innerHTML = saved;
        // stale proposal buttons don't survive a restart — disable them
        msgs.querySelectorAll('.aw-card-actions button').forEach(b => b.disabled = true);
        msgs.scrollTop = msgs.scrollHeight;
    }
}

function addMsg(who, html) {
    const msgs = document.getElementById('aw-chat-messages');
    const div = document.createElement('div');
    div.className = `aw-msg aw-${who}`;
    div.innerHTML = html;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    saveTranscript();
    return div;
}

// single API helper — one place for headers, JSON, and error shape (rule from
// expert review of the owner's chat-mvp project)
async function awApi(path, body) {
    const resp = await fetch(path, body === undefined ? {} : {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => ({}));
    return { status: resp.status, data };
}

function esc(s) {
    return (s == null ? '' : String(s))
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// --- send + live feed -------------------------------------------------------
async function onSend(e) {
    e.preventDefault();
    const input = document.getElementById('aw-chat-input');
    const text = input.value.trim();
    if (!text || AW.busy) return;
    input.value = '';
    addMsg('user', esc(text));
    setBusyUI(true);

    const status = addMsg('status',
        '<i class="fas fa-circle-notch fa-spin"></i> <span class="aw-status-text">thinking…</span>');
    try {
        const { status: httpStatus, data } = await awApi('/api/agent/chat',
            { message: text, session_id: AW.sessionId });
        if (httpStatus !== 202) {  // refusal / wrapped / busy / budget / error
            status.remove();
            if (data.type === 'wrapped') {
                addMsg('agent', esc(data.response));
                openWrapped(data.period, data.force, data.start, data.end);
                return;
            }
            addMsg(data.type === 'refusal' || data.type === 'planning' ? 'agent' : 'system',
                   esc(data.response || data.error || 'Something went wrong.'));
            return;
        }
        AW.sessionId = data.session_id;
        localStorage.setItem('aw_session_id', AW.sessionId);
        AW.runId = data.run_id;
        const agent = data.route === 'playlist_request' ? 'DJ' : 'Analyst';
        await pollRun(data.run_id, status, agent);
    } catch (err) {
        status.remove();
        addMsg('system', 'Network error — is the server up?');
    } finally {
        setBusyUI(false);
        AW.runId = null;
        saveTranscript();
    }
}

async function pollRun(runId, status, agent) {
    const deadline = Date.now() + 5 * 60 * 1000;  // hard stop: 5 minutes
    let misses = 0;
    for (;;) {
        await new Promise(r => setTimeout(r, 1200));
        if (Date.now() > deadline) {
            status.remove();
            addMsg('system', 'The run timed out — send your message again.');
            return;
        }
        let data;
        try {
            const r = await awApi(`/api/agent/run/${runId}`);
            data = r.data;
            if (r.status === 404 || data.error === 'Unknown run.') {
                status.remove();
                addMsg('system', 'That run was lost (server restarted) — send your message again.');
                return;
            }
        } catch {
            if (++misses > 5) {
                status.remove();
                addMsg('system', 'Lost connection to the server — send your message again.');
                return;
            }
            continue;
        }

        const now = (data.steps || []).length ? data.steps[data.steps.length - 1] : 'thinking';
        const label = `${agent || 'Agent'} · ${now}…`;
        const textEl = status.querySelector('.aw-status-text');
        if (textEl && textEl.dataset.label !== label) {
            // swap only the text — the spinner element persists, so its
            // rotation never restarts and the line reads as one flow
            textEl.dataset.label = label;
            textEl.innerHTML = `<strong>${esc(agent || 'Agent')}</strong> · ${esc(now)}…`;
        }
        document.getElementById('aw-chat-messages').scrollTop = 1e9;

        if (data.done) {
            status.remove();
            if (data.error) addMsg('system', esc(data.error));
            else renderResult(data.result);
            return;
        }
    }
}

function renderResult(result) {
    if (result.type === 'playlist_proposal') {
        addMsg('agent', esc(result.response));
        renderProposal(result.proposal_id, result.playlist);
    } else {
        addMsg('agent', esc(result.response) +
            (result.withheld ? '<div class="aw-withheld">proposal withheld — constraints not met</div>' : ''));
    }
}

function renderProposal(proposalId, pl) {
    const tracks = (pl.tracks || []).map(t => `
        <div class="aw-track">
            <span class="aw-fam aw-fam-${esc(t.familiarity)}">${esc(t.familiarity || '?')}</span>
            <span class="aw-track-name" title="${esc(t.reason)}">${esc(t.track_name)}
                <em>— ${esc(t.artist_name)}</em></span>
        </div>`).join('');
    const card = addMsg('card', `
        <div class="aw-card-head">
            <strong>${esc(pl.name)}</strong>
            <span class="aw-duration">${esc(Math.round(pl.total_duration_min || 0))} min</span>
        </div>
        <div class="aw-card-desc">${esc(pl.description)}</div>
        <div class="aw-tracks">${tracks}</div>
        <div class="aw-card-actions">
            <button class="aw-approve"><i class="fas fa-check"></i> Approve &amp; push</button>
            <button class="aw-reject"><i class="fas fa-times"></i> Reject</button>
        </div>
        <div class="aw-reject-box aw-hidden">
            <input placeholder="why? (optional — the DJ learns from this)" maxlength="200">
            <button class="aw-reject-send">Send</button>
        </div>`);
    card.querySelector('.aw-approve').onclick = () => approve(proposalId, card);
    card.querySelector('.aw-reject').onclick = () =>
        card.querySelector('.aw-reject-box').classList.remove('aw-hidden');
    card.querySelector('.aw-reject-send').onclick = () => reject(proposalId, card);
    saveTranscript();
}

async function approve(proposalId, card) {
    setCardBusy(card, true);
    try {
        const { data } = await awApi('/api/agent/approve', { proposal_id: proposalId });
        if (data.type === 'pushed') {
            card.querySelector('.aw-card-actions').innerHTML =
                `<a class="aw-pushed" href="${esc(data.url)}" target="_blank">
                    <i class="fab fa-spotify"></i> Pushed — open in Spotify</a>`;
        } else {
            addMsg('system', esc(data.error || 'Push failed — try again.'));
            setCardBusy(card, false);
        }
    } catch { addMsg('system', 'Network error during push.'); setCardBusy(card, false); }
    saveTranscript();
}

async function reject(proposalId, card) {
    const reason = card.querySelector('.aw-reject-box input').value.trim();
    setCardBusy(card, true);
    try {
        await awApi('/api/agent/reject', { proposal_id: proposalId, reason });
        card.querySelector('.aw-card-actions').innerHTML =
            '<span class="aw-rejected">rejected — the DJ will learn from it</span>';
        card.querySelector('.aw-reject-box').classList.add('aw-hidden');
    } catch { addMsg('system', 'Network error.'); setCardBusy(card, false); }
    saveTranscript();
}

function setCardBusy(card, busy) {
    card.querySelectorAll('button').forEach(b => b.disabled = busy);
}
