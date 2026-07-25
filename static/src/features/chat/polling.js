// The two live-progress loops. Both are bounded by a deadline so a silent
// server can never leave the panel spinning forever.

import { ApiError } from '../../api/client.js';
import { deadline, sleep } from '../../shared/async.js';
import { esc } from '../../shared/dom.js';
import * as api from './api.js';
import {
    MAX_CONSECUTIVE_MISSES,
    PLAN_POLL_MS,
    POLL_TIMEOUT_MS,
    RUN_POLL_MS,
} from './constants.js';
import * as view from './view.js';

export async function pollRun(runId, status, agent, { onResult }) {
    const expiry = deadline(POLL_TIMEOUT_MS);
    let misses = 0;

    for (;;) {
        await sleep(RUN_POLL_MS);
        if (expiry.expired()) {
            return fail(status, 'The run timed out — send your message again.');
        }

        let run;
        try {
            run = await api.fetchRun(runId);
        } catch (error) {
            if (error instanceof ApiError && error.status === 404) {
                return fail(status,
                    'That run was lost (server restarted) — send your message again.');
            }
            if (++misses > MAX_CONSECUTIVE_MISSES) {
                return fail(status, 'Lost connection to the server — send your message again.');
            }
            continue;
        }
        misses = 0;

        const steps = run.steps || [];
        view.updateStatus(status, agent, steps.length ? steps[steps.length - 1] : 'thinking');
        view.scrollToLatest();

        if (run.done) {
            status.remove();
            if (run.error) view.addMessage('system', esc(run.error));
            else onResult(run.result);
            return;
        }
    }
}

// The Planner streams proposals in as it builds them, so each one is rendered
// the moment it lands rather than waiting for the whole plan.
export async function pollPlan(status, { onProposal }) {
    const expiry = deadline(POLL_TIMEOUT_MS);
    const seen = new Set();
    const setStatus = (text) => view.updateStatus(status, 'Planner', text);
    setStatus('reading your calendar');

    for (;;) {
        await sleep(PLAN_POLL_MS);
        if (expiry.expired()) {
            return fail(status, 'Planning timed out — try again.');
        }

        let plan;
        try {
            plan = await api.fetchPlanProposals();
        } catch {
            continue;
        }

        for (const proposal of plan.proposals || []) {
            if (seen.has(proposal.proposal_id)) continue;
            seen.add(proposal.proposal_id);
            announceBlock(proposal.block || {});
            onProposal(proposal.proposal_id, proposal.playlist);
        }
        view.scrollToLatest();

        if (!plan.running) {
            status.remove();
            if (plan.error) view.addMessage('system', esc(plan.error));
            else if (!seen.size) view.addMessage('agent', EMPTY_PLAN);
            return;
        }
        setStatus(`building playlists (${seen.size} ready)`);
    }
}

const EMPTY_PLAN =
    "Nothing to soundtrack tomorrow — your calendar's clear or only has blocks " +
    "where music doesn't fit.";

function announceBlock(block) {
    view.addMessage('agent',
        `🗓 for <strong>${esc(block.title || 'your block')}</strong>` +
        (block.start ? ` at ${esc(block.start)}` : ''));
}

function fail(status, message) {
    status.remove();
    view.addMessage('system', message);
}
