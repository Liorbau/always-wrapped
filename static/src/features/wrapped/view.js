// DOM for the story overlay. The four async states (loading / story / empty /
// error) each render explicitly.

import { byId, esc } from '../../shared/dom.js';
import { prefersReducedMotion } from '../../shared/motion.js';

export const CARD_MS = 6000;

const COUNT_UP_STEPS = 40;
const COUNT_UP_MS = 1100;
const COUNT_UP_MIN = 10;

let countTimer = null;

export function mountOverlay() {
    const overlay = byId('aw-wrapped-overlay');
    if (!overlay) return null;
    overlay.innerHTML = `
        <button id="aw-wrapped-pause" class="aw-hidden" title="Pause"><i class="fas fa-pause"></i></button>
        <button id="aw-wrapped-close" title="Close">&times;</button>
        <div id="aw-wrapped-frame" class="w-frame w-d1"></div>`;
    return overlay;
}

export function showOverlay() {
    byId('aw-wrapped-overlay').classList.remove('aw-hidden');
    document.body.style.overflow = 'hidden';
}

export function hideOverlay() {
    byId('aw-wrapped-overlay').classList.add('aw-hidden');
    document.body.style.overflow = '';
}

export function renderState(state, message) {
    const frame = byId('aw-wrapped-frame');
    frame.className = 'w-frame w-d1';
    frame.style.cssText = '';
    byId('aw-wrapped-pause')?.classList.add('aw-hidden');

    const panels = {
        loading: '<i class="fas fa-circle-notch fa-spin"></i><p>Wrapping your music…</p>',
        empty: `<i class="fas fa-record-vinyl"></i><p>${esc(message)}</p>`,
        error: `<i class="fas fa-triangle-exclamation"></i><p>${esc(message)}</p>`,
    };
    frame.innerHTML = `<div class="w-center">${panels[state]}</div>`;
}

export function renderStory(cards, { onPrevious, onNext, onHold }) {
    const frame = byId('aw-wrapped-frame');
    frame.innerHTML = `
        <div class="w-bars">${cards.map(() =>
            '<div class="w-bar-track"><div class="w-bar-fill"></div></div>').join('')}</div>
        <div class="w-card" id="w-card"></div>
        <div class="w-tap w-tap-left"></div><div class="w-tap w-tap-right"></div>`;
    frame.querySelector('.w-tap-left').addEventListener('click', onPrevious);
    frame.querySelector('.w-tap-right').addEventListener('click', onNext);
    for (const type of ['pointerdown', 'pointerup']) frame.addEventListener(type, onHold);
    byId('aw-wrapped-pause')?.classList.remove('aw-hidden');
}

export function renderCard(cards, index, { paused }) {
    const card = cards[index];
    byId('aw-wrapped-frame').className = `w-frame ${card.design || 'w-d1'}`;
    byId('w-card').innerHTML = `<div class="w-card-inner ${card.cls}">${card.html}</div>`;
    countUpHeadline();
    renderProgress(index, paused);
}

function renderProgress(index, paused) {
    document.querySelectorAll('.w-bar-track').forEach((track, position) => {
        const fill = track.firstElementChild;
        fill.style.animation = 'none';
        void fill.offsetWidth;  // force a reflow so the animation restarts
        if (position < index) {
            fill.style.width = '100%';
        } else if (position === index) {
            fill.style.width = '';
            fill.style.animation = `w-fill ${CARD_MS}ms linear`;
            if (paused) fill.style.animationPlayState = 'paused';
        } else {
            fill.style.width = '0';
        }
    });
}

export function setBarPlayState(index, paused) {
    const fill = document.querySelectorAll('.w-bar-fill')[index];
    if (fill) fill.style.animationPlayState = paused ? 'paused' : 'running';
}

export function renderPauseButton(paused) {
    const button = byId('aw-wrapped-pause');
    if (!button) return;
    button.innerHTML = paused ? '<i class="fas fa-play"></i>' : '<i class="fas fa-pause"></i>';
    button.title = paused ? 'Play' : 'Pause';
}

function countUpHeadline() {
    if (prefersReducedMotion()) return;
    clearInterval(countTimer);

    const element = document.querySelector('#w-card .w-big');
    if (!element) return;
    const raw = element.textContent.trim();
    if (!/^[0-9,]+$/.test(raw)) return;  // skip clock faces like "07:00"
    const target = parseInt(raw.replace(/,/g, ''), 10);
    if (!target || target < COUNT_UP_MIN) return;

    let step = 0;
    element.textContent = '0';
    countTimer = setInterval(() => {
        step++;
        const eased = 1 - Math.pow(1 - step / COUNT_UP_STEPS, 3);
        element.textContent = Math.round(target * eased).toLocaleString();
        if (step >= COUNT_UP_STEPS) {
            element.textContent = target.toLocaleString();
            clearInterval(countTimer);
        }
    }, COUNT_UP_MS / COUNT_UP_STEPS);
}
