// The "CREATE WRAP" dropdown in the hero. Its only job is turning a click into
// an open request for the story.
//
// Handlers bind to the elements themselves rather than delegating from the nav:
// the nav toggles open/closed on every click it sees, so a child that must keep
// the menu open has to stop the event before it gets there.

import { byId } from '../../shared/dom.js';

export function init({ onOpen }) {
    const nav = byId('nav-wrapped');
    if (!nav) return;

    nav.addEventListener('click', (event) => {
        nav.classList.toggle('open');
        event.stopPropagation();
    });
    window.addEventListener('click', () => nav.classList.remove('open'));

    nav.querySelectorAll('[data-wrapped-period]').forEach((item) => {
        item.addEventListener('click', () => onOpen({ period: item.dataset.wrappedPeriod }));
    });

    const customPanel = nav.querySelector('.nav-wrapped-custom');
    nav.querySelector('[data-wrapped-custom-toggle]')?.addEventListener('click', (event) => {
        event.stopPropagation();
        customPanel.classList.toggle('aw-hidden');
    });
    customPanel?.addEventListener('click', (event) => event.stopPropagation());

    nav.querySelector('[data-wrapped-custom-go]')?.addEventListener('click', () => {
        const start = byId('w-custom-start').value;
        const end = byId('w-custom-end').value;
        const problem = validate(start, end);
        if (problem) return window.alert(problem);
        nav.classList.remove('open');
        onOpen({ period: 'custom', start, end });
    });
}

function validate(start, end) {
    if (!start || !end) return 'Pick both dates.';
    if (start > end) return 'Start date is after end date.';
    return null;
}
