import { byId } from '../../shared/dom.js';
import * as api from './api.js';
import { EVENT_STAGGER_MS, POLL_MS, TRIGGER_COOLDOWN_MS } from './constants.js';
import * as view from './view.js';

const board = { lastEventId: 0 };

export function init() {
    if (!byId('ag-board')) return;
    view.layout();
    window.addEventListener('resize', view.layout);
    wireEvaluatorTrigger();
    tick();
    setInterval(tick, POLL_MS);
}

async function tick() {
    let activity;
    try {
        activity = await api.fetchActivity();
    } catch {
        return;  // a dropped poll is not worth disturbing the board over
    }

    view.clearHighlights();
    view.renderActive(activity.active);
    view.renderCosts(activity);
    renderFreshEvents(activity.events);
}

function renderFreshEvents(events) {
    const fresh = events.filter((event) => event.id > board.lastEventId);
    if (!fresh.length) return;

    board.lastEventId = events[events.length - 1].id;
    view.renderFeed(events);
    // stagger so a burst of events reads as a sequence rather than one flash
    fresh.forEach((event, index) =>
        setTimeout(() => view.flashForEvent(event), index * EVENT_STAGGER_MS));
}

function wireEvaluatorTrigger() {
    const button = byId('ag-run-eval');
    if (!button) return;

    button.addEventListener('click', async (event) => {
        event.stopPropagation();
        button.disabled = true;
        try {
            await api.triggerEvaluator();
        } catch (error) {
            window.alert(error.message);
        }
        setTimeout(() => { button.disabled = false; }, TRIGGER_COOLDOWN_MS);
    });
}
