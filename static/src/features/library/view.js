// DOM only. Knows nothing about URLs, ranges, or when to fetch.

import { esc } from '../../shared/dom.js';

const SPOTIFY_URL = 'https://open.spotify.com';

export function renderSkeletons(container, rows, withRank = true) {
    let markup = '';
    for (let i = 0; i < rows; i++) {
        markup += `
        <div class="skeleton-row">
            ${withRank ? '<div class="skeleton" style="width:24px;height:16px"></div>' : ''}
            <div class="skeleton" style="width:44px;height:44px"></div>
            <div style="flex:1;display:flex;flex-direction:column;gap:6px">
                <div class="skeleton" style="width:${55 + (i * 13) % 30}%;height:12px"></div>
                <div class="skeleton" style="width:${25 + (i * 7) % 20}%;height:10px"></div>
            </div>
        </div>`;
    }
    container.innerHTML = markup;
}

export function renderMessage(container, message) {
    container.innerHTML = `<p class="loading">${esc(message)}</p>`;
}

export function renderRecentPlays(container, tracks) {
    renderRows(container, tracks, (track) => ({
        kind: 'track',
        id: track.track_id,
        html: `${artwork(track.album_image_url, false)}
            <div><span class="song-name">${esc(track.track_name)}</span>
            <span class="artist-name">${esc(track.artist_name)}</span></div>`,
    }));
}

export function renderTopSongs(container, tracks) {
    renderRows(container, tracks, (track, index) => ({
        kind: 'track',
        id: track.track_id,
        html: `<div class="rank-num">${index + 1}</div>
            ${artwork(track.album_image_url, false)}
            <div><span class="song-name">${esc(track.track_name)}</span>
            <span class="track-meta">${esc(track.play_count)} plays</span>
            <span class="track-meta">${esc(track.artist_name)}</span></div>`,
    }));
}

export function renderTopArtists(container, artists) {
    renderRows(container, artists, (artist, index) => ({
        kind: 'artist',
        id: artist.artist_id,
        html: `<div class="rank-num">${index + 1}</div>
            ${artwork(artist.artist_image_url, true)}
            <div><span class="song-name">${esc(artist.artist_name)}</span>
            <span class="track-meta">${esc(artist.play_count)} plays</span></div>`,
    }));
}

function renderRows(container, items, describe) {
    container.innerHTML = '';
    items.forEach((item, index) => {
        const { kind, id, html } = describe(item, index);
        const card = document.createElement('div');
        card.className = 'track-item';
        card.innerHTML = html;
        linkToSpotify(card, kind, id);
        container.appendChild(card);
    });
}

function artwork(url, rounded) {
    if (url) {
        return `<img src="${esc(url)}" class="track-img" alt="" loading="lazy"` +
               (rounded ? ' style="border-radius:50%"' : '') + '>';
    }
    return rounded
        ? '<div class="artist-icon"><i class="fas fa-microphone"></i></div>'
        : '<div class="track-img-fallback"><i class="fas fa-music"></i></div>';
}

function linkToSpotify(card, kind, id) {
    if (!id) return;
    card.classList.add('track-link');
    card.title = 'Open in Spotify';
    card.addEventListener('click', () =>
        window.open(`${SPOTIFY_URL}/${kind}/${encodeURIComponent(id)}`, '_blank'));
}
