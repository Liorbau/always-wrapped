import { sleep } from '../../shared/async.js';
import * as api from './api.js';
import * as view from './view.js';

const CYCLE_MS = 15000;
const SETTLE_MS = 350;

const state = { locked: false, timer: null };

export async function init() {
    const card = document.querySelector('.insight-card');
    if (!card) return;
    card.addEventListener('mouseenter', cycle);

    try {
        view.show(await api.fetchInsight());
    } catch {
        // the markup ships with a default line; leaving it is the honest fallback
    }
    restartTimer();
}

function restartTimer() {
    clearInterval(state.timer);
    state.timer = setInterval(cycle, CYCLE_MS);
}

export async function cycle() {
    if (state.locked) return;
    state.locked = true;
    restartTimer();
    view.slideOut();

    let insight;
    try {
        insight = await api.fetchInsight();
    } catch {
        view.settle();
        state.locked = false;
        return;
    }

    await sleep(view.SLIDE_DURATION_MS);
    view.slideIn(insight);
    await sleep(SETTLE_MS);
    state.locked = false;
}
