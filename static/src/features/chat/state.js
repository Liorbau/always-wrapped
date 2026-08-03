// Wiring: send a message, route the reply, and own the HITL approve/reject.

import { ApiError } from '../../api/client.js';
import { byId, esc } from '../../shared/dom.js';
import * as api from './api.js';
import { AGENT_LABELS, SESSION_KEY } from './constants.js';
import { pollPlan, pollRun } from './polling.js';
import * as view from './view.js';

// A budget refusal is the DJ speaking, not an app failure, so it reads as a
// message from the agent rather than a system error.
const AGENT_VOICE_CODES = new Set(['BUDGET_EXHAUSTED']);

const chat = {
    sessionId: localStorage.getItem(SESSION_KEY) || null,
    busy: false,
    runId: null,
    unlocked: false,
};

let requestWrapped = () => {};

export function init({ onWrappedRequest } = {}) {
    requestWrapped = onWrappedRequest || requestWrapped;
    const mounted = view.mountPanel({
        onSend: send,
        onStop: stop,
        onClear: clearConversation,
        onToggle: toggle,
        onUnlock: unlock,
        onPlantimeSave: savePlantime,
        onPlantimeOff: turnPlantimeOff,
    });
    if (mounted) {
        view.restoreTranscript();
        refreshUnlockStatus();
    }
}

async function refreshUnlockStatus() {
    try {
        const status = await api.unlockStatus();
        chat.unlocked = Boolean(status.unlocked);
    } catch {
        chat.unlocked = false;
    }
}

async function refreshPlantime() {
    try {
        view.renderPlantime(await api.fetchPlannerTime());
    } catch {
        // unlocked gate already covers auth errors
    }
}

async function toggle() {
    view.togglePanel();
    if (!view.panelIsOpen()) return;
    await refreshUnlockStatus();
    if (chat.unlocked) {
        view.hideUnlockGate();
        await refreshPlantime();
    } else {
        view.showUnlockGate();
    }
}

async function unlock(event) {
    event.preventDefault();
    const token = view.unlockInputValue();
    if (!token) {
        view.showUnlockGate('Enter the password.');
        return;
    }
    view.setUnlockBusy(true);
    try {
        await api.unlock(token);
        chat.unlocked = true;
        view.hideUnlockGate();
        await refreshPlantime();
    } catch (error) {
        chat.unlocked = false;
        view.showUnlockGate(error.message || 'Wrong password.');
    } finally {
        view.setUnlockBusy(false);
    }
}

async function savePlantime() {
    const at = view.plantimeInputValue();
    if (!at) {
        view.addMessage('system', 'Pick a time first, or tap Off.');
        return;
    }
    view.setPlantimeBusy(true);
    try {
        const schedule = await api.setPlannerTime(at);
        view.renderPlantime(schedule);
        view.addMessage('system', `Nightly Planner set to ${schedule.at}.`);
    } catch (error) {
        showError(error);
    } finally {
        view.setPlantimeBusy(false);
    }
}

async function turnPlantimeOff() {
    view.setPlantimeBusy(true);
    try {
        const schedule = await api.setPlannerTime(null);
        view.renderPlantime(schedule);
        view.addMessage('system', 'Nightly Planner turned off.');
    } catch (error) {
        showError(error);
    } finally {
        view.setPlantimeBusy(false);
    }
}

function setBusy(busy) {
    chat.busy = busy;
    view.setBusy(busy);
}

function clearConversation() {
    if (!window.confirm('Clear the conversation? The DJ forgets this chat.')) return;
    view.clearMessages();
    localStorage.removeItem(SESSION_KEY);
    chat.sessionId = null;
    setBusy(false);  // also unsticks a wedged client
    view.addMessage('system', '— conversation cleared —');
}

async function stop() {
    if (!chat.runId) return;
    try {
        await api.stopRun(chat.runId);
    } catch {
        // the poll loop still sees the run finish
    }
}

async function send(event) {
    event.preventDefault();
    const input = byId('aw-chat-input');
    const text = input.value.trim();
    if (!text || chat.busy) return;

    input.value = '';
    view.addMessage('user', esc(text));
    setBusy(true);
    const status = view.addStatusLine();

    try {
        await dispatch(await api.sendMessage(text, chat.sessionId), status);
    } catch (error) {
        status.remove();
        showError(error);
    } finally {
        setBusy(false);
        chat.runId = null;
        view.saveTranscript();
    }
}

async function dispatch(reply, status) {
    if (reply.type === 'wrapped') {
        status.remove();
        view.addMessage('agent', esc(reply.response));
        requestWrapped({
            period: reply.period,
            force: reply.force,
            start: reply.start,
            end: reply.end,
        });
        return;
    }
    if (reply.type === 'planning') {
        view.addMessage('agent', esc(reply.response));
        return pollPlan(status, { onProposal: showProposal });
    }
    if (reply.type === 'refusal') {
        status.remove();
        view.addMessage('agent', esc(reply.response));
        return;
    }
    if (reply.type === 'plantime') {
        status.remove();
        view.addMessage('system', esc(reply.response));
        view.renderPlantime(reply);
        return;
    }
    if (reply.type === 'spend') {
        status.remove();
        view.addMessage('system', esc(reply.response));
        return;
    }

    chat.sessionId = reply.session_id;
    localStorage.setItem(SESSION_KEY, chat.sessionId);
    chat.runId = reply.run_id;
    return pollRun(reply.run_id, status, AGENT_LABELS[reply.route] || 'Agent', {
        onResult: showResult,
    });
}

function showResult(result) {
    const proposal = view.renderResult(result);
    if (proposal) showProposal(proposal.proposalId, proposal.playlist);
}

function showProposal(proposalId, playlist) {
    view.renderProposal(proposalId, playlist, { onApprove: approve, onReject: reject });
}

async function approve(proposalId, card) {
    view.setCardBusy(card, true);
    try {
        const pushed = await api.approve(proposalId);
        view.markPushed(card, pushed.url);
    } catch (error) {
        showError(error);
        view.setCardBusy(card, false);
    }
}

async function reject(proposalId, card) {
    const reason = view.rejectionReason(card);
    view.setCardBusy(card, true);
    try {
        await api.reject(proposalId, reason);
        view.markRejected(card);
    } catch (error) {
        showError(error);
        view.setCardBusy(card, false);
    }
}

function showError(error) {
    const agentVoice = error instanceof ApiError && AGENT_VOICE_CODES.has(error.code);
    view.addMessage(agentVoice ? 'agent' : 'system', esc(error.message));
}
