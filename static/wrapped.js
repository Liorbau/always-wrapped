// Wrapped story: phone-frame modal over the dashboard.
// States: loading | story | empty | error (rendered explicitly, per house rules).
// v3: curated fixed designs (w-d1..w-d5) assigned per card type — the LLM
// still writes all copy, but no longer chooses colors. Adds a functioning
// pause/play button (plus existing hold-to-pause and keyboard support).

const WRAP = { cards: [], idx: 0, timer: null, paused: false, userPaused: false, countTimer: null };
const CARD_MS = 6000;
const W_REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function countUpBig() {
    if (W_REDUCED) return;
    clearInterval(WRAP.countTimer);
    const el = document.querySelector('#w-card .w-big');
    if (!el) return;
    const raw = el.textContent.trim();
    if (!/^[0-9,]+$/.test(raw)) return;          // skip clock faces like "07:00"
    const target = parseInt(raw.replace(/,/g, ''), 10);
    if (!target || target < 10) return;
    const steps = 40, dur = 1100;
    let i = 0;
    el.textContent = '0';
    WRAP.countTimer = setInterval(() => {
        i++;
        const p = 1 - Math.pow(1 - i / steps, 3);  // cubic ease-out
        el.textContent = Math.round(target * p).toLocaleString();
        if (i >= steps) {
            el.textContent = target.toLocaleString();
            clearInterval(WRAP.countTimer);
        }
    }, dur / steps);
}


function toggleCustomRange(e) {
    e.stopPropagation();
    document.querySelector('.nav-wrapped-custom').classList.toggle('aw-hidden');
}

function openCustomWrapped() {
    const start = document.getElementById('w-custom-start').value;
    const end = document.getElementById('w-custom-end').value;
    if (!start || !end) return alert('Pick both dates.');
    if (start > end) return alert('Start date is after end date.');
    document.getElementById('nav-wrapped').classList.remove('open');
    openWrapped('custom', false, start, end);
}

function openWrapped(period, force, start, end) {
    const overlay = document.getElementById('aw-wrapped-overlay');
    overlay.classList.remove('aw-hidden');
    document.body.style.overflow = 'hidden';
    setUserPaused(false, true);
    renderWrappedState('loading');
    const range = period === 'custom' ? `&start=${start}&end=${end}` : '';
    fetch(`/api/wrapped?period=${encodeURIComponent(period || 'week')}${force ? '&force=1' : ''}${range}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) return renderWrappedState('error', data.error);
            if (data.empty) return renderWrappedState('empty', data.message);
            startStory(data);
        })
        .catch(() => renderWrappedState('error', 'Network error.'));
}

function closeWrapped() {
    clearTimeout(WRAP.timer);
    WRAP.timer = null;
    WRAP.userPaused = false;
    document.getElementById('aw-wrapped-overlay').classList.add('aw-hidden');
    document.body.style.overflow = '';
}

function renderWrappedState(state, message) {
    const frame = document.getElementById('aw-wrapped-frame');
    frame.className = 'w-frame w-d1';
    frame.style.cssText = '';
    const pauseBtn = document.getElementById('aw-wrapped-pause');
    if (pauseBtn) pauseBtn.classList.add('aw-hidden');
    if (state === 'loading') {
        frame.innerHTML = '<div class="w-center"><i class="fas fa-circle-notch fa-spin"></i><p>Wrapping your music…</p></div>';
    } else if (state === 'empty') {
        frame.innerHTML = `<div class="w-center"><i class="fas fa-record-vinyl"></i><p>${esc(message)}</p></div>`;
    } else if (state === 'error') {
        frame.innerHTML = `<div class="w-center"><i class="fas fa-triangle-exclamation"></i><p>${esc(message)}</p></div>`;
    }
}

// --- pause / play -----------------------------------------------------------
function setUserPaused(v, silentReset) {
    WRAP.userPaused = v;
    const btn = document.getElementById('aw-wrapped-pause');
    if (btn) {
        btn.innerHTML = v ? '<i class="fas fa-play"></i>' : '<i class="fas fa-pause"></i>';
        btn.title = v ? 'Play' : 'Pause';
    }
    if (silentReset) return;
    const fill = document.querySelectorAll('.w-bar-fill')[WRAP.idx];
    if (fill) fill.style.animationPlayState = v ? 'paused' : 'running';
    if (v) { clearTimeout(WRAP.timer); WRAP.timer = null; }
    else advanceTimer();
}

function togglePause() { setUserPaused(!WRAP.userPaused); }

// --- card assembly from the edition payload --------------------------------
// Curated design per card type (matches wrapped.css w-d1..w-d5):
// d1 hot pink + spinning blocks · d2 red-orange + zigzag · d3 bubblegum list
// d4 purple + rainbow ring · d5 green checker
function buildCards(ed) {
    const s = ed.stats, c = ed.copy || {}, e = esc(ed.theme && ed.theme.emoji || '🎧');
    const line = (id, i, fb) => ((c[id] || [])[i]) || fb;
    const top5 = (list, key) => list.map((x, i) =>
        `<div class="w-row"><span class="w-rank">${i + 1}</span>${esc(x[key])}<em>${x.plays}</em></div>`).join('');
    const cards = [
        { cls: 'w-title', design: 'w-d1', html: `<div class="w-emoji">${e}</div><h1>${esc(line('title', 0, 'Your Wrapped'))}</h1><p>${esc(line('title', 1, s.label))}</p>` },
        { cls: '', design: 'w-d2', html: `<h2>${esc(line('volume', 0, 'Tracks played'))}</h2><div class="w-big">${s.plays}</div><p>plays</p><p class="w-sub">${esc(line('volume', 1, `last period: ${s.prev_plays}`))}</p>` },
    ];
    if (s.top_songs[0]) cards.push({ cls: '', design: 'w-d4', html: `<h2>${esc(line('top_song', 0, 'Your #1 song'))}</h2>${s.top_songs[0].image ? `<img class="w-art" src="${esc(s.top_songs[0].image)}">` : ''}<div class="w-name">${esc(s.top_songs[0].track)}</div><p>${esc(s.top_songs[0].artist)} · ${s.top_songs[0].plays} plays</p>` });
    if (s.top_songs.length > 1) cards.push({ cls: '', design: 'w-d3', html: `<h2>${esc(line('top_songs', 0, 'Top songs'))}</h2><div class="w-list">${top5(s.top_songs, 'track')}</div>` });
    if (s.top_artists[0]) cards.push({ cls: '', design: 'w-d4', html: `<h2>${esc(line('top_artist', 0, 'Your #1 artist'))}</h2>${s.top_artists[0].image ? `<img class="w-art w-round" src="${esc(s.top_artists[0].image)}">` : ''}<div class="w-name">${esc(s.top_artists[0].artist)}</div><p>${s.top_artists[0].plays} plays</p>` });
    if (s.top_artists.length > 1) cards.push({ cls: '', design: 'w-d3', html: `<h2>${esc(line('top_artists', 0, 'Top artists'))}</h2><div class="w-list">${top5(s.top_artists, 'artist')}</div>` });
    if (s.eras.length) {
        const total = s.eras.reduce((a, x) => a + x.plays, 0);
        cards.push({ cls: '', design: 'w-d5', html: `<h2>${esc(line('eras', 0, 'Time traveler'))}</h2><div class="w-list">${s.eras.map(x => `<div class="w-row"><span class="w-era">${esc(x.decade)}</span><span class="w-bar" style="width:${Math.round(60 * x.plays / total)}%"></span><em>${Math.round(100 * x.plays / total)}%</em></div>`).join('')}</div>` });
    }
    if (s.peak_hour !== null) cards.push({ cls: '', design: 'w-d2', html: `<h2>${esc(line('clock', 0, 'Your listening clock'))}</h2><div class="w-big">${String(s.peak_hour).padStart(2, '0')}:00</div><p>peak hour · busiest: ${esc(s.peak_day)}</p>` });
    cards.push({ cls: 'w-title', design: 'w-d5', html: `<div class="w-emoji">${e}</div><h1>${esc(line('closing', 0, 'Keep listening.'))}</h1><p>${esc(line('closing', 1, 'ALWAYS WRAPPED.'))}</p>` });
    return cards;
}

function startStory(edition) {
    const frame = document.getElementById('aw-wrapped-frame');
    // v3: colors are curated per card design — the LLM palette is ignored.
    WRAP.cards = buildCards(edition);
    WRAP.idx = 0;
    frame.innerHTML = `
        <div class="w-bars">${WRAP.cards.map(() => '<div class="w-bar-track"><div class="w-bar-fill"></div></div>').join('')}</div>
        <div class="w-card" id="w-card"></div>
        <div class="w-tap w-tap-left"></div><div class="w-tap w-tap-right"></div>`;
    frame.querySelector('.w-tap-left').addEventListener('click', () => showCard(WRAP.idx - 1));
    frame.querySelector('.w-tap-right').addEventListener('click', () => showCard(WRAP.idx + 1));
    for (const ev of ['pointerdown', 'pointerup']) frame.addEventListener(ev, holdPause);
    const pauseBtn = document.getElementById('aw-wrapped-pause');
    if (pauseBtn) pauseBtn.classList.remove('aw-hidden');
    setUserPaused(false, true);
    showCard(0);
}

function holdPause(e) {
    if (WRAP.userPaused) return;  // explicit pause wins over hold-to-pause
    WRAP.paused = e.type === 'pointerdown';
    const fill = document.querySelectorAll('.w-bar-fill')[WRAP.idx];
    if (fill) fill.style.animationPlayState = WRAP.paused ? 'paused' : 'running';
    if (!WRAP.paused && WRAP.timer === null) advanceTimer(); // resume
}

function showCard(i) {
    if (i < 0) i = 0;
    if (i >= WRAP.cards.length) return closeWrapped(); // story finished
    WRAP.idx = i;
    const frame = document.getElementById('aw-wrapped-frame');
    frame.className = `w-frame ${WRAP.cards[i].design || 'w-d1'}`;
    document.getElementById('w-card').innerHTML =
        `<div class="w-card-inner ${WRAP.cards[i].cls}">${WRAP.cards[i].html}</div>`;
    countUpBig();
    document.querySelectorAll('.w-bar-track').forEach((track, j) => {
        const fill = track.firstElementChild;
        fill.style.animation = 'none';
        void fill.offsetWidth; // restart animation
        if (j < i) fill.style.width = '100%';
        else if (j === i) {
            fill.style.width = '';
            fill.style.animation = `w-fill ${CARD_MS}ms linear`;
            if (WRAP.userPaused) fill.style.animationPlayState = 'paused';
        }
        else fill.style.width = '0';
    });
    advanceTimer();
}

function advanceTimer() {
    clearTimeout(WRAP.timer);
    if (WRAP.userPaused) { WRAP.timer = null; return; }
    WRAP.timer = setTimeout(() => {
        WRAP.timer = null;
        if (!WRAP.paused && !WRAP.userPaused) showCard(WRAP.idx + 1);
    }, CARD_MS);
}

// --- entry points ------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    const nav = document.getElementById('nav-wrapped');
    if (nav) {
        nav.addEventListener('click', e => { nav.classList.toggle('open'); e.stopPropagation(); });
        window.addEventListener('click', () => nav.classList.remove('open'));
    }
    const root = document.getElementById('aw-wrapped-overlay');
    if (!root) return;
    root.innerHTML = `
        <button id="aw-wrapped-pause" class="aw-hidden" title="Pause"><i class="fas fa-pause"></i></button>
        <button id="aw-wrapped-close" title="Close">&times;</button>
        <div id="aw-wrapped-frame" class="w-frame w-d1"></div>`;
    document.getElementById('aw-wrapped-close').addEventListener('click', closeWrapped);
    document.getElementById('aw-wrapped-pause').addEventListener('click', togglePause);
    document.addEventListener('keydown', e => {
        if (root.classList.contains('aw-hidden')) return;
        if (e.key === 'Escape') closeWrapped();
        if (e.key === 'ArrowRight') showCard(WRAP.idx + 1);
        if (e.key === 'ArrowLeft') showCard(WRAP.idx - 1);
        if (e.key === ' ') { e.preventDefault(); togglePause(); }
    });
});
