// Always Wrapped — script.js (patched)
// Changes vs original: esc() everywhere (XSS), skeleton loaders, track-meta
// class instead of inline styles, lazy/alt images, local art fallback,
// canvas pauses when tab hidden + respects prefers-reduced-motion.

// Track the currently selected time range
let currentTimeRange = 'all_time';

document.addEventListener('DOMContentLoaded', () => {
    fetchRecentTracks();
    fetchTopSongs('all_time');
    fetchTopArtists('all_time');
    initEnergyRibbons();
    loadInsight();
});

// --- HELPERS ---
function esc(s) {
    return (s == null ? '' : String(s))
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}


function spotifyLink(card, kind, id) {
    if (!id) return;
    card.classList.add('track-link');
    card.title = 'Open in Spotify';
    card.addEventListener('click', () =>
        window.open(`https://open.spotify.com/${kind}/${encodeURIComponent(id)}`, '_blank'));
}

function trackArt(url, rounded) {
    if (url) {
        return `<img src="${esc(url)}" class="track-img" alt="" loading="lazy"` +
               (rounded ? ' style="border-radius:50%"' : '') + '>';
    }
    return rounded
        ? '<div class="artist-icon"><i class="fas fa-microphone"></i></div>'
        : '<div class="track-img-fallback"><i class="fas fa-music"></i></div>';
}

function skeletonRows(n, withRank = true) {
    let html = '';
    for (let i = 0; i < n; i++) {
        html += `
        <div class="skeleton-row">
            ${withRank ? '<div class="skeleton" style="width:24px;height:16px"></div>' : ''}
            <div class="skeleton" style="width:44px;height:44px"></div>
            <div style="flex:1;display:flex;flex-direction:column;gap:6px">
                <div class="skeleton" style="width:${55 + (i * 13) % 30}%;height:12px"></div>
                <div class="skeleton" style="width:${25 + (i * 7) % 20}%;height:10px"></div>
            </div>
        </div>`;
    }
    return html;
}

// --- DROPDOWN LOGIC ---
function toggleDropdown() {
    const dropdown = document.querySelector('.custom-dropdown-container');
    dropdown.classList.toggle('open');
}

function selectRange(value, text, element) {
    // 1. Update the button text
    document.getElementById('selected-range-text').innerText = text;

    // 2. Update the visual "active" state in the list
    document.querySelectorAll('.dropdown-item').forEach(item => {
        item.classList.remove('active');
    });
    element.classList.add('active');

    // 3. Update the tracked time range
    currentTimeRange = value;

    // 4. Close the menu
    toggleDropdown();

    // 5. Fetch new data
    fetchTopSongs(value);
    fetchTopArtists(value);
}

// Close dropdown if clicking outside
window.addEventListener('click', (e) => {
    const dropdown = document.querySelector('.custom-dropdown-container');
    if (dropdown && !dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});


// --- CANVAS ANIMATION ---
function initEnergyRibbons() {
    const canvas = document.getElementById('energy-ribbon');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let time = 0;
    let rafId = null;
    const config = {
        lineCount: 40, amplitude: 150, frequency: 0.002, speed: 0.0002, color: '30, 215, 96'
    };
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        if (reducedMotion) drawFrame();  // static frame stays correct on resize
    }
    window.addEventListener('resize', resize);

    function drawFrame() {
        ctx.fillStyle = '#050505';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.lineWidth = 1;
        const centerY = canvas.height / 2;
        const scrollY = window.scrollY;
        for (let i = 0; i < config.lineCount; i++) {
            const opacity = 1 - Math.abs((i - config.lineCount / 2) / (config.lineCount / 2));
            ctx.beginPath();
            ctx.strokeStyle = `rgba(${config.color}, ${opacity * 0.6})`;
            for (let x = 0; x <= canvas.width; x += 5) {
                let y = centerY + Math.sin(x * config.frequency + time + (i * 0.05)) * config.amplitude;
                y += Math.cos(x * config.frequency * 0.5 - time * 0.5) * (config.amplitude * 0.5);
                const direction = i % 2 === 0 ? 1 : -0.5;
                const parallaxShift = scrollY * 0.5 * direction * (1 + i * 0.01);
                y += parallaxShift - (canvas.height * 0.2);
                y += (i - config.lineCount / 2) * 8;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
    }

    function loop() {
        drawFrame();
        time += config.speed * 10;
        rafId = requestAnimationFrame(loop);
    }

    // Pause the 60fps loop while the tab is hidden — saves battery.
    document.addEventListener('visibilitychange', () => {
        if (reducedMotion) return;
        if (document.hidden) {
            if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
        } else if (!rafId) {
            loop();
        }
    });

    resize();
    if (reducedMotion) drawFrame();  // one static frame, no loop
    else loop();
}

async function triggerRefresh() {
    const btn = document.getElementById('refresh-btn');
    const originalText = btn.innerHTML;
    btn.style.width = btn.offsetWidth + 'px';  // lock size across text swaps
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SYNCING...';
    btn.disabled = true;
    try {
        const response = await fetch('/api/refresh', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            fetchRecentTracks();
            // Refresh charts with currently selected time range
            fetchTopSongs(currentTimeRange);
            fetchTopArtists(currentTimeRange);
            btn.innerHTML = '<i class="fas fa-check"></i> DONE';
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error(error);
        btn.innerHTML = '<i class="fas fa-times"></i> FAILED';
    }
    setTimeout(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }, 2000);
}

async function fetchRecentTracks() {
    const container = document.getElementById('recent-tracks-list');
    container.innerHTML = skeletonRows(4, false);
    try {
        const response = await fetch('/api/history');
        const tracks = await response.json();
        container.innerHTML = '';
        tracks.forEach(track => {
            const card = document.createElement('div');
            card.className = 'track-item';
            card.innerHTML = `
                ${trackArt(track.album_image_url, false)}
                <div><span class="song-name">${esc(track.track_name)}</span><span class="artist-name">${esc(track.artist_name)}</span></div>
            `;
            spotifyLink(card, 'track', track.track_id);
            container.appendChild(card);
        });
    } catch (e) { container.innerHTML = '<p class="loading">Error loading.</p>'; }
}

async function fetchTopSongs(timeRange = 'all_time') {
    const container = document.getElementById('top-songs-list');
    container.innerHTML = skeletonRows(5);
    try {
        const response = await fetch(`/api/stats/top-songs?range=${timeRange}`);
        const tracks = await response.json();
        container.innerHTML = '';
        if (tracks.length === 0) {
            container.innerHTML = '<p class="loading">No data for this period.</p>';
            return;
        }
        tracks.forEach((track, index) => {
            const card = document.createElement('div');
            card.className = 'track-item';
            card.innerHTML = `
                <div class="rank-num">${index + 1}</div>
                ${trackArt(track.album_image_url, false)}
                <div><span class="song-name">${esc(track.track_name)}</span><span class="track-meta">${esc(track.play_count)} plays</span><span class="track-meta">${esc(track.artist_name)}</span></div>
            `;
            spotifyLink(card, 'track', track.track_id);
            container.appendChild(card);
        });
    } catch (e) { container.innerHTML = '<p class="loading">Error loading.</p>'; }
}

// --- INSIGHT CARD ---
let insightLocked = false;
let insightTimer = null;

function startInsightTimer() {
    clearInterval(insightTimer);
    insightTimer = setInterval(cycleInsight, 15000);
}

async function loadInsight() {
    try {
        const res = await fetch('/api/insight');
        const data = await res.json();
        document.getElementById('insight-text').innerHTML = data.text;
        document.getElementById('insight-icon-el').className = `fas fa-${data.icon} insight-icon`;
    } catch (e) { /* keep default text */ }
    startInsightTimer();
}

async function cycleInsight() {
    if (insightLocked) return;
    insightLocked = true;
    startInsightTimer();

    const content = document.getElementById('insight-content');

    content.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
    content.style.transform = 'translateY(-15px)';
    content.style.opacity = '0';

    try {
        const res = await fetch('/api/insight');
        const data = await res.json();

        setTimeout(() => {
            document.getElementById('insight-text').innerHTML = data.text;
            document.getElementById('insight-icon-el').className = `fas fa-${data.icon} insight-icon`;

            content.style.transition = 'none';
            content.style.transform = 'translateY(15px)';

            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    content.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
                    content.style.transform = 'translateY(0)';
                    content.style.opacity = '1';
                    setTimeout(() => { insightLocked = false; }, 350);
                });
            });
        }, 300);
    } catch (e) {
        content.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
        content.style.transform = 'translateY(0)';
        content.style.opacity = '1';
        insightLocked = false;
    }
}

// --- SEARCH LOGIC ---
let searchTimeRange = 'all_time';
let searchDebounceTimer = null;

function handleSearch(query) {
    clearTimeout(searchDebounceTimer);
    const dropdown = document.getElementById('search-dropdown');
    if (!query.trim()) {
        dropdown.classList.remove('open');
        return;
    }
    searchDebounceTimer = setTimeout(() => performSearch(query.trim()), 300);
}

async function performSearch(query) {
    const dropdown = document.getElementById('search-dropdown');
    const resultsContainer = document.getElementById('search-results');
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&range=${searchTimeRange}`);
        const results = await response.json();
        dropdown.classList.add('open');
        resultsContainer.innerHTML = '';
        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="search-no-results">No results found for this period.</div>';
            return;
        }
        results.forEach(item => {
            const div = document.createElement('div');
            div.className = 'search-result-item';
            const icon = item.type === 'artist' ? 'fa-microphone' : 'fa-music';
            const name = item.type === 'song' ? item.track_name : item.artist_name;
            const detail = item.type === 'song' ? `${item.artist_name} · ${item.play_count} plays` : `Artist · ${item.play_count} plays`;
            div.innerHTML = `
                <i class="fas ${icon} search-result-icon"></i>
                <div class="search-result-info">
                    <span class="search-result-name">${esc(name)}</span>
                    <span class="search-result-type">${esc(detail)}</span>
                </div>
                <span class="search-result-rank">#${esc(item.rank)}</span>
            `;
            resultsContainer.appendChild(div);
        });
    } catch (e) {
        dropdown.classList.add('open');
        resultsContainer.innerHTML = '<div class="search-no-results">Error searching.</div>';
    }
}

function selectSearchRange(range, element) {
    searchTimeRange = range;
    document.querySelectorAll('.search-tab').forEach(t => t.classList.remove('active'));
    element.classList.add('active');
    const query = document.getElementById('search-input').value.trim();
    if (query) performSearch(query);
}

window.addEventListener('click', (e) => {
    const container = document.querySelector('.search-container');
    const dropdown = document.getElementById('search-dropdown');
    if (container && !container.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});

async function fetchTopArtists(timeRange = 'all_time') {
    const container = document.getElementById('top-artists-list');
    container.innerHTML = skeletonRows(5);
    try {
        const response = await fetch(`/api/stats/top-artists?range=${timeRange}`);
        const artists = await response.json();
        container.innerHTML = '';
        if (artists.length === 0) {
            container.innerHTML = '<p class="loading">No data for this period.</p>';
            return;
        }
        artists.forEach((artist, index) => {
            const card = document.createElement('div');
            card.className = 'track-item';
            card.innerHTML = `
                <div class="rank-num">${index + 1}</div>
                ${trackArt(artist.artist_image_url, true)}
                <div><span class="song-name">${esc(artist.artist_name)}</span><span class="track-meta">${esc(artist.play_count)} plays</span></div>
            `;
            spotifyLink(card, 'artist', artist.artist_id);
            container.appendChild(card);
        });
    } catch (e) { container.innerHTML = '<p class="loading">Error loading.</p>'; }
}
