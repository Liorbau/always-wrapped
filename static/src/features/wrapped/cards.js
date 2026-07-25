// Pure transform: an edition payload becomes an ordered list of story cards.
// Designs are curated per card type (see wrapped.css w-d1..w-d5) — the model
// writes the copy, never the colours.

import { esc } from '../../shared/dom.js';

const DEFAULT_EMOJI = '🎧';
const ERA_BAR_MAX_PCT = 60;

export function buildCards(edition) {
    const stats = edition.stats;
    const copy = edition.copy || {};
    const emoji = esc((edition.theme && edition.theme.emoji) || DEFAULT_EMOJI);
    const line = (id, index, fallback) => ((copy[id] || [])[index]) || fallback;

    const cards = [
        titleCard(emoji, line('title', 0, 'Your Wrapped'), line('title', 1, stats.label)),
        volumeCard(stats, line),
    ];
    if (stats.top_songs[0]) cards.push(topSongCard(stats.top_songs[0], line));
    if (stats.top_songs.length > 1) cards.push(listCard(line('top_songs', 0, 'Top songs'), stats.top_songs, 'track'));
    if (stats.top_artists[0]) cards.push(topArtistCard(stats.top_artists[0], line));
    if (stats.top_artists.length > 1) cards.push(listCard(line('top_artists', 0, 'Top artists'), stats.top_artists, 'artist'));
    if (stats.eras.length) cards.push(erasCard(stats.eras, line));
    if (stats.peak_hour !== null) cards.push(clockCard(stats, line));
    cards.push(closingCard(emoji, line('closing', 0, 'Keep listening.'),
                           line('closing', 1, 'ALWAYS WRAPPED.')));
    return cards;
}

function titleCard(emoji, heading, sub) {
    return {
        cls: 'w-title', design: 'w-d1',
        html: `<div class="w-emoji">${emoji}</div><h1>${esc(heading)}</h1><p>${esc(sub)}</p>`,
    };
}

function closingCard(emoji, heading, sub) {
    return {
        cls: 'w-title', design: 'w-d5',
        html: `<div class="w-emoji">${emoji}</div><h1>${esc(heading)}</h1><p>${esc(sub)}</p>`,
    };
}

function volumeCard(stats, line) {
    return {
        cls: '', design: 'w-d2',
        html: `<h2>${esc(line('volume', 0, 'Tracks played'))}</h2>
            <div class="w-big">${stats.plays}</div><p>plays</p>
            <p class="w-sub">${esc(line('volume', 1, `last period: ${stats.prev_plays}`))}</p>`,
    };
}

function topSongCard(song, line) {
    return {
        cls: '', design: 'w-d4',
        html: `<h2>${esc(line('top_song', 0, 'Your #1 song'))}</h2>
            ${song.image ? `<img class="w-art" src="${esc(song.image)}" alt="">` : ''}
            <div class="w-name">${esc(song.track)}</div>
            <p>${esc(song.artist)} · ${song.plays} plays</p>`,
    };
}

function topArtistCard(artist, line) {
    return {
        cls: '', design: 'w-d4',
        html: `<h2>${esc(line('top_artist', 0, 'Your #1 artist'))}</h2>
            ${artist.image ? `<img class="w-art w-round" src="${esc(artist.image)}" alt="">` : ''}
            <div class="w-name">${esc(artist.artist)}</div>
            <p>${artist.plays} plays</p>`,
    };
}

function listCard(heading, items, key) {
    const rows = items.map((item, index) =>
        `<div class="w-row"><span class="w-rank">${index + 1}</span>${esc(item[key])}` +
        `<em>${item.plays}</em></div>`).join('');
    return {
        cls: '', design: 'w-d3',
        html: `<h2>${esc(heading)}</h2><div class="w-list">${rows}</div>`,
    };
}

function erasCard(eras, line) {
    const total = eras.reduce((sum, era) => sum + era.plays, 0);
    const rows = eras.map((era) =>
        `<div class="w-row"><span class="w-era">${esc(era.decade)}</span>` +
        `<span class="w-bar" style="width:${Math.round(ERA_BAR_MAX_PCT * era.plays / total)}%"></span>` +
        `<em>${Math.round(100 * era.plays / total)}%</em></div>`).join('');
    return {
        cls: '', design: 'w-d5',
        html: `<h2>${esc(line('eras', 0, 'Time traveler'))}</h2><div class="w-list">${rows}</div>`,
    };
}

function clockCard(stats, line) {
    return {
        cls: '', design: 'w-d2',
        html: `<h2>${esc(line('clock', 0, 'Your listening clock'))}</h2>
            <div class="w-big">${String(stats.peak_hour).padStart(2, '0')}:00</div>
            <p>peak hour · busiest: ${esc(stats.peak_day)}</p>`,
    };
}
