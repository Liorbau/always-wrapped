import { byId } from '../../shared/dom.js';
import * as api from './api.js';
import { buildCards } from './cards.js';
import * as view from './view.js';

const story = { cards: [], index: 0, timer: null, held: false, userPaused: false };

export function init() {
    if (!view.mountOverlay()) return;
    byId('aw-wrapped-close').addEventListener('click', close);
    byId('aw-wrapped-pause').addEventListener('click', togglePause);
    document.addEventListener('keydown', onKeyDown);
}

export async function open({ period, force = false, start, end }) {
    view.showOverlay();
    setUserPaused(false, { silent: true });
    view.renderState('loading');

    let edition;
    try {
        edition = await api.fetchEdition({ period, force, start, end });
    } catch (error) {
        return view.renderState('error', error.message);
    }
    if (edition.empty) return view.renderState('empty', edition.message);
    start_(edition);
}

export function close() {
    clearTimeout(story.timer);
    story.timer = null;
    story.userPaused = false;
    view.hideOverlay();
}

function start_(edition) {
    story.cards = buildCards(edition);
    story.index = 0;
    view.renderStory(story.cards, {
        onPrevious: () => showCard(story.index - 1),
        onNext: () => showCard(story.index + 1),
        onHold: onHold,
    });
    setUserPaused(false, { silent: true });
    showCard(0);
}

function showCard(index) {
    if (index < 0) index = 0;
    if (index >= story.cards.length) return close();  // story finished
    story.index = index;
    view.renderCard(story.cards, index, { paused: story.userPaused });
    scheduleAdvance();
}

function scheduleAdvance() {
    clearTimeout(story.timer);
    if (story.userPaused) {
        story.timer = null;
        return;
    }
    story.timer = setTimeout(() => {
        story.timer = null;
        if (!story.held && !story.userPaused) showCard(story.index + 1);
    }, view.CARD_MS);
}

function setUserPaused(paused, { silent = false } = {}) {
    story.userPaused = paused;
    view.renderPauseButton(paused);
    if (silent) return;
    view.setBarPlayState(story.index, paused);
    if (paused) {
        clearTimeout(story.timer);
        story.timer = null;
    } else {
        scheduleAdvance();
    }
}

function togglePause() {
    setUserPaused(!story.userPaused);
}

function onHold(event) {
    if (story.userPaused) return;  // an explicit pause outranks hold-to-pause
    story.held = event.type === 'pointerdown';
    view.setBarPlayState(story.index, story.held);
    if (!story.held && story.timer === null) scheduleAdvance();
}

function onKeyDown(event) {
    if (byId('aw-wrapped-overlay').classList.contains('aw-hidden')) return;
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowRight') showCard(story.index + 1);
    if (event.key === 'ArrowLeft') showCard(story.index - 1);
    if (event.key === ' ') {
        event.preventDefault();
        togglePause();
    }
}
