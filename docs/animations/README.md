# Animaciones de referencia (web)

Kit fuera del nucleo Qt: no se empaqueta ni entra a `requirements.txt`.

- `template.tsx`: transicion de pagina fade/slide (200-300ms).
- `RouteProgress.tsx`: barra `scaleX` (solo transform).
- `StaggerList.tsx`: entradas escalonadas 50ms.
- `ActionButton.tsx`: micro-interacciones hover/tap + loading.
- `Reveal.tsx`: reveal por scroll (`once: true`).
- `tailwind.keyframes.ts`: keyframes solo transform/opacity.

Reglas: solo `transform`/`opacity`, `prefers-reduced-motion` via
`useReducedMotion()` + `motion-reduce:` y media query global.
Equivalente Qt en TRAKKART: feedback instantaneo por QSS +
`TRAKKART_REDUCED_MOTION=1` (preview 700ms, video/resize 500ms).
