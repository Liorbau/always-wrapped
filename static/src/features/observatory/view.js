import { byId, esc } from '../../shared/dom.js';
import { EDGES, FLASH_MS, NODE_BY_AGENT, TOOL_NODE_BY_ACTIVITY } from './constants.js';

export function layout() {
    const board = byId('ag-board');
    if (!board) return;
    const bounds = board.getBoundingClientRect();

    document.querySelectorAll('.ag-node').forEach((node) => {
        node.style.left = `${node.dataset.x}%`;
        node.style.top = `${node.dataset.y}%`;
    });

    byId('ag-edges').innerHTML = EDGES.map(([from, to, variant]) => {
        const a = byId(from);
        const b = byId(to);
        const x1 = (parseFloat(a.dataset.x) / 100) * bounds.width;
        const y1 = (parseFloat(a.dataset.y) / 100) * bounds.height;
        const x2 = (parseFloat(b.dataset.x) / 100) * bounds.width;
        const y2 = (parseFloat(b.dataset.y) / 100) * bounds.height;
        return `<line id="edge-${from}-${to}" class="${variant || ''}" ` +
               `x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"></line>`;
    }).join('');
}

export function clearHighlights() {
    document.querySelectorAll('.ag-node').forEach((n) => n.classList.remove('active'));
    document.querySelectorAll('.ag-doing').forEach((chip) => chip.remove());
}

export function renderActive(active) {
    const line = byId('ag-active-line');
    const runCost = byId('ag-run-cost');

    if (!active) {
        line.innerHTML =
            '<i class="fas fa-moon"></i> agents idle — talk to the chat on the dashboard';
        runCost.classList.remove('hot');
        return;
    }

    const agentNode = byId(`node-${active.agent}`);
    if (agentNode) {
        agentNode.classList.add('active');
        const chip = document.createElement('div');
        chip.className = 'ag-doing';
        chip.textContent = `${active.doing}…`;
        agentNode.appendChild(chip);
    }

    const toolId = TOOL_NODE_BY_ACTIVITY[active.doing];
    if (toolId) {
        byId(toolId)?.classList.add('active');
        byId(`edge-node-${active.agent}-${toolId}`)?.classList.add('hot');
    }

    line.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> ' +
        `<b>${esc(active.agent.toUpperCase())}</b> · ${esc(active.doing)} · step ${active.steps}`;
    runCost.textContent = `$${active.cost.toFixed(3)}`;
    runCost.classList.add('hot');
}

export function renderCosts({ daily_cost: spent, daily_budget: budget }) {
    // spent is null when the ledger is unreadable; showing $0.00 would imply
    // the opposite of what is actually known
    byId('ag-day-cost').textContent = spent == null ? '—' : `$${spent.toFixed(2)}`;
    byId('ag-budget').textContent = `$${budget.toFixed(0)}`;
}

export function renderFeed(events) {
    byId('ag-feed').innerHTML = events.slice().reverse().map((event) =>
        `<div class="ag-ev"><time>${esc(event.ts)}</time>` +
        `<span class="who">${esc(event.node)}</span><p>${esc(event.text)}</p></div>`
    ).join('');
}

export function flashForEvent(event) {
    flashNode(NODE_BY_AGENT[event.node]);

    const toolCall = event.text.match(/^tool: (\w+)/);
    if (!toolCall) return;
    flashNode(`node-${toolCall[1]}`);
    const edge = byId(`edge-node-${event.node}-node-${toolCall[1]}`);
    if (edge) {
        edge.classList.add('hot');
        setTimeout(() => edge.classList.remove('hot'), FLASH_MS);
    }
}

function flashNode(id) {
    const node = byId(id);
    if (!node) return;
    node.classList.add('flash');
    setTimeout(() => node.classList.remove('flash'), FLASH_MS);
}
