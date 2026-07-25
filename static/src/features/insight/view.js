// The insight text is server-rendered HTML (the server escapes the names it
// interpolates), so it is assigned as markup on purpose.

import { byId } from '../../shared/dom.js';

const SLIDE_MS = 300;

export function show(insight) {
    byId('insight-text').innerHTML = insight.text;
    byId('insight-icon-el').className = `fas fa-${insight.icon} insight-icon`;
}

export function slideOut() {
    const content = byId('insight-content');
    content.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
    content.style.transform = 'translateY(-15px)';
    content.style.opacity = '0';
}

export function slideIn(insight) {
    const content = byId('insight-content');
    show(insight);
    content.style.transition = 'none';
    content.style.transform = 'translateY(15px)';
    requestAnimationFrame(() => requestAnimationFrame(() => {
        content.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
        content.style.transform = 'translateY(0)';
        content.style.opacity = '1';
    }));
}

export function settle() {
    const content = byId('insight-content');
    content.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
    content.style.transform = 'translateY(0)';
    content.style.opacity = '1';
}

export const SLIDE_DURATION_MS = SLIDE_MS;
