// Fetch, decide, hand the result to the view. The selected range is the single
// source of truth for both charts; the range picker only reports changes to it.

import { byId, onClick, onClickOutside } from '../../shared/dom.js';
import * as api from './api.js';
import * as view from './view.js';

const SYNC_RESET_MS = 2000;
const DEFAULT_RANGE = 'all_time';

const state = { range: DEFAULT_RANGE };

export function init() {
    wireRangePicker();
    wireSyncButton();
    reloadAll();
}

export function reloadAll() {
    loadRecentPlays();
    loadTopSongs();
    loadTopArtists();
}

async function loadRecentPlays() {
    const container = byId('recent-tracks-list');
    view.renderSkeletons(container, 4, false);
    try {
        view.renderRecentPlays(container, await api.fetchRecentPlays());
    } catch (error) {
        view.renderMessage(container, error.message);
    }
}

async function loadTopSongs() {
    const container = byId('top-songs-list');
    view.renderSkeletons(container, 5);
    try {
        const songs = await api.fetchTopSongs(state.range);
        if (!songs.length) return view.renderMessage(container, 'No data for this period.');
        view.renderTopSongs(container, songs);
    } catch (error) {
        view.renderMessage(container, error.message);
    }
}

async function loadTopArtists() {
    const container = byId('top-artists-list');
    view.renderSkeletons(container, 5);
    try {
        const artists = await api.fetchTopArtists(state.range);
        if (!artists.length) return view.renderMessage(container, 'No data for this period.');
        view.renderTopArtists(container, artists);
    } catch (error) {
        view.renderMessage(container, error.message);
    }
}

function wireRangePicker() {
    const dropdown = document.querySelector('.custom-dropdown-container');
    if (!dropdown) return;

    const toggle = () => dropdown.classList.toggle('open');
    onClick(dropdown, '[data-range-toggle]', toggle);
    dropdown.querySelector('[data-range-toggle]')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggle();
        }
    });

    onClick(dropdown, '[data-range]', (item) => {
        state.range = item.dataset.range;
        // The visible label is the item's own text, so there is no second
        // lookup table to drift out of sync with the markup.
        byId('selected-range-text').textContent = item.textContent.trim();
        dropdown.querySelectorAll('[data-range]').forEach((el) =>
            el.classList.toggle('active', el === item));
        dropdown.classList.remove('open');
        loadTopSongs();
        loadTopArtists();
    });

    onClickOutside(dropdown, () => dropdown.classList.remove('open'));
}

function wireSyncButton() {
    const button = byId('refresh-btn');
    if (!button) return;

    button.addEventListener('click', async () => {
        const original = button.innerHTML;
        button.style.width = `${button.offsetWidth}px`;  // lock size across text swaps
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SYNCING...';
        button.disabled = true;
        try {
            await api.syncSpotify();
            reloadAll();
            button.innerHTML = '<i class="fas fa-check"></i> DONE';
        } catch {
            button.innerHTML = '<i class="fas fa-times"></i> FAILED';
        }
        setTimeout(() => {
            button.innerHTML = original;
            button.disabled = false;
        }, SYNC_RESET_MS);
    });
}
