import { byId, esc } from '../../shared/dom.js';

export function open() {
    byId('search-dropdown').classList.add('open');
}

export function close() {
    byId('search-dropdown').classList.remove('open');
}

export function renderNotice(message) {
    open();
    byId('search-results').innerHTML = `<div class="search-no-results">${esc(message)}</div>`;
}

export function renderResults(results) {
    open();
    if (!results.length) return renderNotice('No results found for this period.');

    byId('search-results').innerHTML = results.map((item) => {
        const isArtist = item.type === 'artist';
        const name = isArtist ? item.artist_name : item.track_name;
        const detail = isArtist
            ? `Artist · ${item.play_count} plays`
            : `${item.artist_name} · ${item.play_count} plays`;
        return `
            <div class="search-result-item">
                <i class="fas ${isArtist ? 'fa-microphone' : 'fa-music'} search-result-icon"></i>
                <div class="search-result-info">
                    <span class="search-result-name">${esc(name)}</span>
                    <span class="search-result-type">${esc(detail)}</span>
                </div>
                <span class="search-result-rank">#${esc(item.rank)}</span>
            </div>`;
    }).join('');
}

export function markActiveRange(chosen) {
    document.querySelectorAll('[data-search-range]').forEach((tab) =>
        tab.classList.toggle('active', tab === chosen));
}
