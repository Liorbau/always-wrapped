document.addEventListener('DOMContentLoaded', () => {
    fetchRecentTracks();
    // Default call with 'all_time'
    fetchTopSongs('all_time');
    fetchTopArtists('all_time');
    initEnergyRibbons();
});

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

    // 3. Close the menu
    toggleDropdown();

    // 4. Fetch new data
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
    let time = 0;
    const config = {
        lineCount: 40, amplitude: 150, frequency: 0.002, speed: 0.0002, color: '30, 215, 96'
    };
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resize);
    resize();
    function draw() {
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
                y += (i - config.lineCount/2) * 8; 
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
        time += config.speed * 10;
        requestAnimationFrame(draw);
    }
    draw();
}

async function triggerRefresh() {
    const btn = document.getElementById('refresh-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> SYNCING...';
    btn.disabled = true;
    try {
        const response = await fetch('/api/refresh', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            fetchRecentTracks();
            // Refresh stats with currently selected range logic if needed, 
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
    try {
        const response = await fetch('/api/history');
        const tracks = await response.json();
        container.innerHTML = '';
        tracks.forEach(track => {
            const card = document.createElement('div');
            card.className = 'track-item';
            const imgUrl = track.album_image_url || 'https://via.placeholder.com/50';
            card.innerHTML = `
                <img src="${imgUrl}" class="track-img">
                <div><span class="song-name">${track.track_name}</span><span class="artist-name">${track.artist_name}</span></div>
            `;
            container.appendChild(card);
        });
    } catch (e) { container.innerHTML = '<p>Error loading.</p>'; }
}

async function fetchTopSongs(timeRange = 'all_time') {
    const container = document.getElementById('top-songs-list');
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
            const imgUrl = track.album_image_url || 'https://via.placeholder.com/50';
            card.innerHTML = `
                <div class="rank-num">#${index + 1}</div>
                <img src="${imgUrl}" class="track-img">
                <div><span class="song-name">${track.track_name}</span><span style="color:#888; font-size:0.8rem">${track.play_count} plays</span></div>
            `;
            container.appendChild(card);
        });
    } catch (e) { container.innerHTML = '<p>Error loading.</p>'; }
}

async function fetchTopArtists(timeRange = 'all_time') {
    const container = document.getElementById('top-artists-list');
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
                <div class="rank-num">#${index + 1}</div>
                <div class="artist-icon"><i class="fas fa-microphone"></i></div>
                <div><span class="song-name">${artist.artist_name}</span><span style="color:#888; font-size:0.8rem">${artist.play_count} plays</span></div>
            `;
            container.appendChild(card);
        });
    } catch (e) { container.innerHTML = '<p>Error loading.</p>'; }
}