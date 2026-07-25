import { byId, onClick, onClickOutside } from '../../shared/dom.js';
import * as api from './api.js';
import * as view from './view.js';

const DEBOUNCE_MS = 300;

const state = { range: 'all_time', debounce: null, requestId: 0 };

export function init() {
    const container = document.querySelector('.search-container');
    const input = byId('search-input');
    if (!container || !input) return;

    input.addEventListener('input', () => onType(input.value));
    onClick(container, '[data-search-range]', (tab) => {
        state.range = tab.dataset.searchRange;
        view.markActiveRange(tab);
        const term = input.value.trim();
        if (term) run(term);
    });
    onClickOutside(container, view.close);
}

function onType(value) {
    clearTimeout(state.debounce);
    if (!value.trim()) return view.close();
    state.debounce = setTimeout(() => run(value.trim()), DEBOUNCE_MS);
}

async function run(term) {
    const requestId = ++state.requestId;
    try {
        const results = await api.searchLibrary(term, state.range);
        if (requestId !== state.requestId) return;  // a newer query superseded this one
        view.renderResults(results);
    } catch (error) {
        if (requestId !== state.requestId) return;
        view.renderNotice(error.message);
    }
}
