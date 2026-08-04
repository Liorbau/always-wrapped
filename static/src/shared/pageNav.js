// Same-origin MPA slide between dashboard ↔ playlists. Direction lives in
// sessionStorage so the destination page can enter the matching way.

const KEY = 'aw-nav-dir';
const MS = 180;

export function initPageNav(leaveLinks) {
    playEnter();
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    for (const { selector, direction } of leaveLinks || []) {
        document.querySelectorAll(selector).forEach((el) => {
            el.addEventListener('click', (event) => {
                if (event.defaultPrevented) return;
                if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                if (event.button !== 0) return;
                if (el.getAttribute('target') === '_blank') return;
                event.preventDefault();
                sessionStorage.setItem(KEY, direction);
                if (reduce) {
                    window.location.href = el.href;
                    return;
                }
                const leave = direction === 'forward' ? 'aw-leave-left' : 'aw-leave-right';
                document.documentElement.classList.add(leave);
                const href = el.href;
                setTimeout(() => { window.location.href = href; }, MS);
            });
        });
    }
}

function playEnter() {
    const dir = sessionStorage.getItem(KEY);
    if (!dir) return;
    sessionStorage.removeItem(KEY);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const enter = dir === 'forward' ? 'aw-enter-from-right' : 'aw-enter-from-left';
    document.documentElement.classList.add(enter);
    setTimeout(() => document.documentElement.classList.remove(enter), MS + 40);
}
