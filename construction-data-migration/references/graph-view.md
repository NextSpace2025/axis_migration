# Reusable local 3D relationship renderer

The public assets `assets/viewer/graph3d.js` and `graph3d.css` contain the reusable
renderer from the local graph work. They contain no company records, source
paths, database or graph dataset. Keep those inputs in the private run directory.
The standard `scripts/view_db.py` table page does not automatically acquire a
graph: these assets attach to an existing graph host with the contract below.

## Host integration

Serve the assets locally through the host's static allowlist. Load the CSS after
the host's graph styles and defer the JavaScript after the graph controller:

```html
<link rel="stylesheet" href="graph3d.css">
<!-- The host's graph controller and table/evidence integration load first. -->
<script src="graph3d.js" defer></script>
```

The single-graph host supplies `window.graphView`:

- `nodes`: Map keyed by string ID, with `{id, label, kind, x, y}`. Kinds are
  `file`, `company`, `site`, optionally `expected`; `x/y` are finite layout seeds.
- `edges`: Map keyed by string ID, with `{id, from, to, label, status, internal}`.
  Endpoints must exist. `observed` is confirmed; other statuses remain dashed.
  Internal document links stay in evidence, not the external graph layout.
- `state`: current `node`, `edge`, `local`, `visibleNodes` and `visibleEdges`.
- `selectNode(id, options)`, `selectEdge(id)`: the host's existing selection,
  table-filter and evidence actions. Node options support `{local: false}`.
- `refresh()`: recomputes visibility and redraws the existing SVG host.

Required DOM IDs: `graph-stage` (positioned container with a nonzero height),
`graph` (existing SVG fallback), `local`, `hover-label`. The CSS also styles the
host's optional `.graph-key`, `.zoom-tools` and `#graph-empty` overlays. Keep an
accessible source list, selection inspector, and confirmed/candidate legend.

When the graph controller updates visibility, dispatch this event after the
update so the renderer sees the same node/edge subset as the table and inspector:

```js
document.dispatchEvent(new CustomEvent('axis:graph-render'));
```

Delegate existing fit/zoom controls when the 3D renderer is available, retaining
their normal SVG behavior otherwise:

```js
function fit() {
  if (window.graph3D) { window.graph3D.fit(); return; }
  // Existing SVG fit implementation.
}
function zoom(factor) {
  if (window.graph3D) { window.graph3D.zoom(factor); return; }
  // Existing SVG zoom implementation.
}
```

For table-row selection, use `{local: !window.graph3D}` if the desired behavior
is to preserve global 3D context and focus the SVG fallback. The explicit local
neighborhood control still applies. Graph-to-table filters remain the host's
responsibility; be clear whether they select related files or exact business rows.

## Behavior and truth boundaries

Drag rotates, Shift-drag pans, wheel/+/- zooms, arrow keys rotate, and Home or
the reset button restores orientation. Selection uses the original host actions.
Reduced-motion disables inertial coasting. If WebGL is missing or its context
is lost, the existing SVG remains available; the host must provide that fallback.

Small matte round points retain file/company/site colors. Capped size variation
uses actual relationship counts. Positions use actual edges for attraction,
repulsion, and connected-component spacing; isolated sources remain present.
Position, depth and size do not imply amounts, source accuracy or business rank.
No new links, identity merges, source readings or database writes occur here.
Labels are reserved for selection and hover. The renderer uses no remote assets
or third-party JavaScript libraries.

The integrated local implementation was verified with real Chrome pointer,
keyboard, zoom, filtering, evidence and WebGL-loss checks. Consumers must verify
their host contract and data separately; copying an asset is not proof that a
different viewer, source scope or hardware configuration has been validated.
