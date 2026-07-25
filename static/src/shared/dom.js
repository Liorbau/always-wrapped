// Tiny DOM helpers shared by every feature. Values in, values out.

export function esc(value) {
    return (value == null ? '' : String(value))
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

export function byId(id) {
    return document.getElementById(id);
}

export function onClickOutside(element, handler) {
    window.addEventListener('click', (event) => {
        if (element && !element.contains(event.target)) handler(event);
    });
}

// Delegated clicks keep handlers off the markup and survive re-renders.
export function onClick(root, selector, handler) {
    if (!root) return;
    root.addEventListener('click', (event) => {
        const match = event.target.closest(selector);
        if (match && root.contains(match)) handler(match, event);
    });
}
