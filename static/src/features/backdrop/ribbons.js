// The animated canvas behind the dashboard. Pauses while the tab is hidden and
// draws a single static frame when the user asked for reduced motion.

import { byId } from '../../shared/dom.js';
import { prefersReducedMotion } from '../../shared/motion.js';

const CONFIG = {
    lineCount: 40,
    amplitude: 150,
    frequency: 0.002,
    speed: 0.0002,
    color: '30, 215, 96',
    background: '#050505',
    stepPx: 5,
};

export function init() {
    const canvas = byId('energy-ribbon');
    if (!canvas) return;

    const context = canvas.getContext('2d');
    const reducedMotion = prefersReducedMotion();
    let time = 0;
    let frameHandle = null;

    function drawFrame() {
        context.fillStyle = CONFIG.background;
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.lineWidth = 1;
        const centerY = canvas.height / 2;
        const scrollY = window.scrollY;

        for (let i = 0; i < CONFIG.lineCount; i++) {
            const fade = 1 - Math.abs((i - CONFIG.lineCount / 2) / (CONFIG.lineCount / 2));
            context.beginPath();
            context.strokeStyle = `rgba(${CONFIG.color}, ${fade * 0.6})`;
            for (let x = 0; x <= canvas.width; x += CONFIG.stepPx) {
                let y = centerY +
                    Math.sin(x * CONFIG.frequency + time + (i * 0.05)) * CONFIG.amplitude;
                y += Math.cos(x * CONFIG.frequency * 0.5 - time * 0.5) * (CONFIG.amplitude * 0.5);
                const direction = i % 2 === 0 ? 1 : -0.5;
                y += scrollY * 0.5 * direction * (1 + i * 0.01) - (canvas.height * 0.2);
                y += (i - CONFIG.lineCount / 2) * 8;
                if (x === 0) context.moveTo(x, y);
                else context.lineTo(x, y);
            }
            context.stroke();
        }
    }

    function loop() {
        drawFrame();
        time += CONFIG.speed * 10;
        frameHandle = requestAnimationFrame(loop);
    }

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        if (reducedMotion) drawFrame();  // the static frame must stay correct
    }

    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', () => {
        if (reducedMotion) return;
        if (document.hidden) {
            if (frameHandle) {
                cancelAnimationFrame(frameHandle);
                frameHandle = null;
            }
        } else if (!frameHandle) {
            loop();
        }
    });

    resize();
    if (reducedMotion) drawFrame();
    else loop();
}
