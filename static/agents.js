// Agent observatory: positions nodes, draws edges, polls /api/agent/activity
// and lights up whoever is working right now.

const EDGES = [
    ['node-dj', 'node-query_history'],
    ['node-dj', 'node-search_spotify'],
    ['node-dj', 'node-artist_top_tracks'],
    ['node-dj', 'node-get_audio_features'],
    ['node-dj', 'node-discover_new_tracks'],
    ['node-analyst', 'node-query_history'],
    ['node-wrapped', 'node-query_history'],
    ['node-evaluator', 'node-query_history'],
    ['node-evaluator', 'node-dj', 'dashed'],       // soft biases feed the DJ
    ['node-planner', 'node-calendar'],             // reads tomorrow's blocks
    ['node-planner', 'node-dj', 'dashed'],         // delegates each brief to the DJ
];

const DOING_TOOL = {
    'exploring your history': 'node-query_history',
    'searching Spotify': 'node-search_spotify',
    'collecting candidate tracks': 'node-artist_top_tracks',
    'checking the mood': 'node-get_audio_features',
    'hunting new music': 'node-discover_new_tracks',
};

function place() {
    const board = document.getElementById('ag-board');
    const svg = document.getElementById('ag-edges');
    const rect = board.getBoundingClientRect();
    document.querySelectorAll('.ag-node').forEach(n => {
        n.style.left = n.dataset.x + '%';
        n.style.top = n.dataset.y + '%';
    });
    svg.innerHTML = EDGES.map(([a, b, cls]) => {
        const na = document.getElementById(a), nb = document.getElementById(b);
        const x1 = (parseFloat(na.dataset.x) / 100) * rect.width;
        const y1 = (parseFloat(na.dataset.y) / 100) * rect.height;
        const x2 = (parseFloat(nb.dataset.x) / 100) * rect.width;
        const y2 = (parseFloat(nb.dataset.y) / 100) * rect.height;
        return `<line id="edge-${a}-${b}" class="${cls || ''}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"></line>`;
    }).join('');
}
window.addEventListener('resize', place);

let lastEventId = 0;

const NODE_OF = {
                  wrapped: 'node-wrapped', evaluator: 'node-evaluator',
                  dj: 'node-dj', analyst: 'node-analyst', planner: 'node-planner' };

function flashNode(id, ms) {
    const n = document.getElementById(id);
    if (!n) return;
    n.classList.add('flash');
    setTimeout(() => n.classList.remove('flash'), ms || 1200);
}

function flashForEvent(ev) {
    // the owning node always flashes
    flashNode(NODE_OF[ev.node]);
    // tool calls flash the tool + heat the edge from the calling agent
    const m = ev.text.match(/^tool: (\w+)/);
    if (m) {
        flashNode(`node-${m[1]}`);
        const edge = document.getElementById(`edge-node-${ev.node}-node-${m[1]}`);
        if (edge) {
            edge.classList.add('hot');
            setTimeout(() => edge.classList.remove('hot'), 1200);
        }
    }
}

async function tick() {
    let data;
    try {
        data = await (await fetch('/api/agent/activity')).json();
    } catch { return; }

    // node highlighting
    document.querySelectorAll('.ag-node').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.ag-doing').forEach(el => el.remove());


    const line = document.getElementById('ag-active-line');
    if (data.active) {
        const agentNode = document.getElementById(`node-${data.active.agent}`);
        if (agentNode) {
            agentNode.classList.add('active');
            const chip = document.createElement('div');
            chip.className = 'ag-doing';
            chip.textContent = data.active.doing + '…';
            agentNode.appendChild(chip);
        }
        const toolId = DOING_TOOL[data.active.doing];
        if (toolId) {
            document.getElementById(toolId).classList.add('active');
            const e = document.getElementById(`edge-node-${data.active.agent}-${toolId}`);
            if (e) e.classList.add('hot');
        }
        line.innerHTML = `<i class="fas fa-circle-notch fa-spin"></i> ` +
            `<b>${data.active.agent.toUpperCase()}</b> · ${data.active.doing} · step ${data.active.steps}`;
        const rc = document.getElementById('ag-run-cost');
        rc.textContent = '$' + data.active.cost.toFixed(3);
        rc.classList.add('hot');
    } else {
        line.innerHTML = '<i class="fas fa-moon"></i> agents idle — talk to the chat on the dashboard';
        document.getElementById('ag-run-cost').classList.remove('hot');
    }

    // costs
    document.getElementById('ag-day-cost').textContent = '$' + data.daily_cost.toFixed(2);
    document.getElementById('ag-budget').textContent = '$' + data.daily_budget.toFixed(0);

    // feed + flashes: process EVERY unseen event (staggered so batches read)
    const fresh = data.events.filter(ev => ev.id > lastEventId);
    if (fresh.length) {
        lastEventId = data.events[data.events.length - 1].id;
        document.getElementById('ag-feed').innerHTML = data.events.slice().reverse().map(ev =>
            `<div class="ag-ev"><time>${ev.ts}</time><span class="who">${ev.node}</span><p>${escA(ev.text)}</p></div>`
        ).join('');
        fresh.forEach((ev, i) => setTimeout(() => flashForEvent(ev), i * 280));
    }
}

function escA(s) {
    return (s == null ? '' : String(s))
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function wireTrigger(btnId, url, busyMsg) {
    document.getElementById(btnId).addEventListener('click', async e => {
        e.stopPropagation();
        const btn = e.currentTarget;
        btn.disabled = true;
        try {
            const r = await fetch(url, { method: 'POST' });
            if (r.status === 409) alert(busyMsg);
            if (r.status === 429) alert('Daily budget reached.');
        } catch { alert('Network error.'); }
        setTimeout(() => { btn.disabled = false; }, 4000);
    });
}
wireTrigger('ag-run-eval', '/api/agent/evaluate', 'An agent is already working — try again in a moment.');
wireTrigger('ag-run-plan', '/api/agent/plan', 'A plan is already running — check the feed.');

place();
tick();
setInterval(tick, 1000);
