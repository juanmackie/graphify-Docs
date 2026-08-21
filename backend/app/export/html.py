"""Self-contained interactive graph.html export — hostable anywhere.

Mirrors Graphify's approach: one HTML file that embeds the graph JSON and loads
the `force-graph` library from a CDN. Open locally or host on GitHub Pages /
Netlify / S3 — anyone with a browser can explore the graph.

Styled with the Tactical Telemetry / CRT Terminal design system.
"""
from __future__ import annotations

import json
from typing import Any

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__ — KNOWLEDGE GRAPH</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet"/>
<script src="https://unpkg.com/force-graph@1"></script>
<style>
  :root { color-scheme: dark; --red:#e61919; --redhi:#ff2a2a; --amber:#ffb000; --dim:#8a8a8a; --line:#2c2c2c; }
  * { box-sizing: border-box; border-radius: 0 !important; }
  html, body { margin: 0; height: 100%; }
  body {
    background: #0a0a0a; color: #eaeaea;
    font-family: 'JetBrains Mono','IBM Plex Mono',Consolas,monospace;
    font-size: 13px;
  }
  body::before {
    content: ''; position: fixed; inset: 0; z-index: 9998; pointer-events: none; opacity: .045;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");
  }
  body::after {
    content: ''; position: fixed; inset: 0; z-index: 9999; pointer-events: none;
    background: repeating-linear-gradient(0deg, rgba(234,234,234,.018) 0 1px, transparent 1px 4px);
  }
  #app { display: flex; flex-direction: column; height: 100%; }
  header {
    display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 50px;
    background: #121212; border-bottom: 2px solid var(--red); flex-shrink: 0;
  }
  header h1 {
    font-size: 13px; margin: 0; letter-spacing: .08em; text-transform: uppercase;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  header h1::before { content: '[ '; color: var(--red); }
  header h1::after { content: ' ]'; color: var(--red); }
  .stat { color: var(--dim); font-size: 10px; letter-spacing: .1em; }
  .flex { flex: 1; }
  main { display: flex; flex: 1; min-height: 0; }
  #side {
    width: 285px; flex-shrink: 0; overflow-y: auto; padding: 10px; gap: 10px;
    display: flex; flex-direction: column; background: #121212; border-right: 1px solid #4a4a4a;
  }
  .box { background: #0f0f0f; border: 1px solid var(--line); padding: 11px; }
  .box h4 {
    margin: 0 0 9px; font-size: 10px; letter-spacing: .16em; text-transform: uppercase;
    padding-bottom: 6px; border-bottom: 1px solid var(--line); font-weight: 700;
  }
  .box h4::before { content: '// '; color: var(--red); }
  input[type=text], select {
    width: 100%; background: #0a0a0a; color: #eaeaea; border: 1px solid #4a4a4a;
    padding: 6px 8px; font-family: inherit; font-size: 11px; letter-spacing: .05em;
    text-transform: uppercase; margin-bottom: 6px;
  }
  input[type=text]:focus, select:focus { border-color: var(--red); outline: none; }
  label.row { display: flex; align-items: center; gap: 6px; font-size: 10px; letter-spacing: .05em; padding: 2px 0; cursor: pointer; }
  .swatch { width: 11px; height: 11px; border: 1px solid rgba(255,255,255,.25); display: inline-block; flex-shrink: 0; }
  .scroll { max-height: 120px; overflow-y: auto; }
  button {
    background: var(--red); color: #fff; border: 1px solid var(--red);
    padding: 7px 11px; font-family: inherit; font-size: 10px; font-weight: 700;
    letter-spacing: .1em; text-transform: uppercase; cursor: pointer;
  }
  button:hover { background: var(--redhi); }
  button.ghost { background: transparent; border: 1px solid #4a4a4a; color: #eaeaea; }
  button.ghost:hover { border-color: var(--red); color: var(--redhi); background: transparent; }
  .path-row { display: flex; gap: 6px; }
  #graph-shell { flex: 1; min-width: 0; position: relative; background: #0b0d0f; background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px); background-size: 32px 32px; }
  #graph { width: 100%; height: 100%; }
  #panel {
    width: 292px; flex-shrink: 0; overflow-y: auto; background: #121212;
    border-left: 2px solid var(--red); padding: 14px; display: none;
  }
  #panel.open { display: block; }
  #panel h3 { margin: 3px 0 10px; word-break: break-word; font-family: 'Archivo Black','Arial Black',sans-serif; font-size: 16px; }
  .kicker { font-size: 9px; letter-spacing: .2em; color: var(--redhi); text-transform: uppercase; }
  .facts { display: grid; grid-template-columns: auto 1fr; gap: 5px 14px; font-size: 11px; margin-bottom: 12px; }
  .facts dt { color: var(--dim); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; }
  .facts dd { margin: 0; text-align: right; }
  .snippet {
    font-size: 11px; color: #8a8a8a; background: #0f0f0f; border: 1px solid var(--line);
    border-left: 3px solid var(--red); padding: 9px; margin-bottom: 12px; letter-spacing: .02em;
  }
  .neighbors { font-size: 11px; }
  .neighbors ul { list-style: none; margin: 8px 0 0; padding: 0; }
  .neighbors li { padding: 3px 0; }
  .neighbors .rel { color: var(--dim); font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }
  .hint { color: var(--dim); font-size: 10px; margin-top: 6px; letter-spacing: .06em; }
  .canvas-meta { position:absolute; z-index:1; top:12px; left:14px; display:flex; align-items:center; gap:7px; padding:6px 9px; background:rgba(10,10,10,.82); border:1px solid var(--line); color:var(--dim); font-size:10px; letter-spacing:.04em; pointer-events:none; }
  .canvas-meta strong { color:#eaeaea; }
  .canvas-actions { position:absolute; z-index:1; top:12px; right:14px; display:flex; gap:5px; }
  .canvas-actions button { background:rgba(10,10,10,.84); }
  .view-mode-buttons { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:4px; margin-bottom:8px; }
  .view-mode-buttons button { min-width:0; padding:7px 5px; font-size:9px; letter-spacing:.04em; line-height:1.25; }
  .view-mode-buttons button.active { background:rgba(230,25,25,.12); border-color:var(--red); color:var(--redhi); }
  .view-summary { margin:0; color:var(--dim); font-size:10px; line-height:1.45; }
  .component-list { display:flex; flex-direction:column; gap:3px; max-height:190px; overflow-y:auto; border-top:1px solid var(--line); padding-top:7px; margin-top:8px; }
  button.component-pick { display:flex; align-items:center; justify-content:space-between; gap:8px; width:100%; padding:6px 7px; background:transparent; border:1px solid transparent; color:#eaeaea; font-size:10px; font-weight:400; letter-spacing:.02em; text-align:left; text-transform:none; }
  button.component-pick:hover, button.component-pick.selected { background:rgba(230,25,25,.12); border-color:var(--red); }
  .component-pick span, .component-pick small { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .component-pick span { min-width:0; }
  .component-pick b { color:var(--redhi); }
  .component-pick small { flex-shrink:0; color:var(--dim); font-size:9px; }
</style>
</head>
<body>
<div id="app">
  <header>
    <h1 title="__TITLE__">__TITLE__</h1>
    <span class="flex"></span>
    <span class="stat" id="stat"></span>
  </header>
  <main>
    <aside id="side">
      <div class="box"><h4>Search</h4><input id="search" type="text" placeholder="SEARCH NODES…"/><div class="hint" id="searchhint"></div></div>
      <div class="box"><h4>Map View</h4><div id="viewModes"></div><div id="components"></div></div>
      <div class="box"><h4>Path Trace</h4>
        <select id="pathA"><option value="">FROM…</option></select>
        <select id="pathB"><option value="">TO…</option></select>
        <button id="pathGo">TRACE</button> <button id="pathClear" class="ghost">CLEAR</button>
        <div class="hint" id="pathhint"></div>
      </div>
      <div class="box"><h4>Edge Filters</h4><div id="filters"></div></div>
      <div class="box"><h4>Communities</h4><div id="legend"></div></div>
    </aside>
    <div id="graph-shell">
      <div id="graph"></div>
      <div class="canvas-meta" id="canvasMeta"></div>
      <div class="canvas-actions">
        <button class="ghost" id="fitCore">FIT CORE</button>
        <button class="ghost" id="fitVisible">FIT VISIBLE</button>
        <button class="ghost" id="resetMap">RESET MAP</button>
      </div>
    </div>
    <aside id="panel"></aside>
  </main>
</div>
<script>
const GRAPH = __GRAPH_JSON__;
(function () {
  const nodes = GRAPH.nodes;
  const links = GRAPH.links;
  const byId = {};
  nodes.forEach(function (n) { byId[n.id] = n; });
  const palette = ['#eaeaea','#ff2a2a','#ffb000','#2de2e6','#7aa2ff','#c792ea','#ff9e64','#e0af68','#7dcfff','#bb9af7','#f7768e','#b8c0e0'];
  const tagColor = { llm: '#eaeaea', cooccurrence: '#5c6370', both: '#ffb000' };
  const TAG_LABEL = { llm: 'LLM EXTRACTED', cooccurrence: 'CO-OCCURRENCE', both: 'LLM + CO-OCCURRENCE' };
  const el = document.getElementById('graph');

  const state = {
    tags: { llm: true, cooccurrence: true, both: true },
    kinds: { assertion: true, association: true },
    relations: {},
    minWeight: 1,
    minConfidence: 0,
    matches: new Set(),
    pathLinks: new Set(),
    pathNodes: new Set(),
    hovered: null,
    selected: null,
    viewMode: 'core',
    componentId: null,
    labelIds: new Set(),
    linkCurvatures: new Map(),
  };
  links.forEach(function (l) { state.relations[l.relation] = true; });

  const endpointId = function (x) { return typeof x === 'string' ? x : x.id; };
  const radius = function (n) { return Math.max(4, Math.min(16, Math.sqrt((n.degree || 0) * 1.4 + Math.log2((n.count || 0) + 1) * 2 + 1) * 2.1)); };
  const linkDirection = function (l) { return l.direction || (l.kind === 'association' || l.tag === 'cooccurrence' ? 'undirected' : 'directed'); };
  const linkKind = function (l) { return l.kind || (linkDirection(l) === 'undirected' ? 'association' : 'assertion'); };
  const linkConfidence = function (l) { return l.quality && typeof l.quality.confidence === 'number' ? l.quality.confidence : 0; };
  const linkProvenance = function (l) { return (l.provenance || [l.tag]).join(' + '); };
  const edgeSignal = function (l) {
    const semanticBoost = linkKind(l) === 'assertion' ? 2 : 1;
    return semanticBoost * (0.5 + linkConfidence(l)) * Math.log2(Math.max(1, l.weight || 1) + 1);
  };

  function connectedComponents(visible) {
    const adjacency = {};
    nodes.forEach(function (n) { adjacency[n.id] = new Set(); });
    visible.forEach(function (l) {
      const s = endpointId(l.source), t = endpointId(l.target);
      if (adjacency[s] && adjacency[t] && s !== t) {
        adjacency[s].add(t); adjacency[t].add(s);
      }
    });
    const seen = new Set(), raw = [];
    nodes.forEach(function (n) {
      if (seen.has(n.id)) return;
      const queue = [n.id], ids = [];
      seen.add(n.id);
      while (queue.length) {
        const current = queue.shift(); ids.push(current);
        (adjacency[current] || []).forEach(function (next) {
          if (!seen.has(next)) { seen.add(next); queue.push(next); }
        });
      }
      const members = new Set(ids);
      const componentLinks = visible.filter(function (l) { return members.has(endpointId(l.source)) && members.has(endpointId(l.target)); });
      const ordered = ids.map(function (id) { return byId[id]; }).filter(Boolean).sort(function (a, b) {
        return (b.degree || 0) - (a.degree || 0) || (b.count || 0) - (a.count || 0) || a.name.localeCompare(b.name);
      });
      raw.push({
        id: ids.slice().sort()[0],
        nodeIds: ids,
        nodeCount: ids.length,
        edgeCount: componentLinks.length,
        signal: componentLinks.reduce(function (sum, l) { return sum + edgeSignal(l); }, 0),
        totalWeight: componentLinks.reduce(function (sum, l) { return sum + (l.weight || 0); }, 0),
        leadName: ordered.length ? ordered[0].name : ids[0],
      });
    });
    return raw.sort(function (a, b) {
      return b.signal - a.signal || b.nodeCount - a.nodeCount || b.edgeCount - a.edgeCount || a.leadName.localeCompare(b.leadName);
    });
  }

  function componentForNode(id, summaries) {
    return summaries.find(function (component) { return component.nodeIds.indexOf(id) !== -1; });
  }

  let componentSummaries = [];
  let currentNodes = nodes;
  let currentLinks = links;
  let shouldFit = true;
  let forcesConfigured = false;
  state.minWeight = links.filter(function (l) { return linkKind(l) === 'association'; }).length > 100 ? 10 : 2;

  function createCommunityForce() {
    let forceNodes = [];
    const force = function (alpha) {
      const communities = Array.from(new Set(forceNodes.map(function (node) { return node.community; }))).sort(function (a, b) { return a - b; });
      if (communities.length <= 1 || forceNodes.length <= 4) return;
      const radius = 190 + Math.sqrt(forceNodes.length) * 7;
      forceNodes.forEach(function (node) {
        const index = communities.indexOf(node.community);
        const angle = -Math.PI / 2 + index / communities.length * Math.PI * 2;
        const targetX = Math.cos(angle) * radius, targetY = Math.sin(angle) * radius;
        node.vx = (node.vx || 0) + (targetX - (node.x || 0)) * alpha * .028;
        node.vy = (node.vy || 0) + (targetY - (node.y || 0)) * alpha * .028;
      });
    };
    force.initialize = function (nodes) { forceNodes = nodes; };
    return force;
  }

  function fitCurrentGraph() {
    shouldFit = false;
    Graph.zoomToFit(500, 40);
    window.setTimeout(function () {
      let cap = null;
      if (currentNodes.length <= 4) cap = 3.5;
      else if (currentNodes.length <= 10) cap = 4.2;
      if (cap && Graph.zoom() > cap) Graph.zoom(cap, 250);
    }, 560);
  }

  const Graph = ForceGraph()(el)
    .width(el.clientWidth)
    .height(el.clientHeight)
    .graphData({ nodes: [], links: [] })
    .backgroundColor('#0a0a0a')
    .nodeVal(radius)
    .nodeLabel(function (n) { return '<b>' + n.name + '</b><br/>' + n.type + ' · DEGREE ' + n.degree + ' · COMM ' + n.community; })
    .linkLabel(function (l) {
      const arrow = linkDirection(l) === 'undirected' ? '↔' : '→';
      return (l.source.name || l.source) + ' —<i>' + l.relation + '</i>' + arrow + ' ' + (l.target.name || l.target)
        + ' (' + linkKind(l) + ', ' + linkProvenance(l) + ', W' + l.weight + ', C' + Math.round(linkConfidence(l) * 100) + '%)';
    })
    .nodeCanvasObjectMode(function () { return 'replace'; })
    .nodeCanvasObject(function (node, ctx, globalScale) {
      if (node.x == null || node.y == null) return;
      const r = radius(node) / globalScale;
      const isPath = state.pathNodes.has(node.id);
      const isMatch = state.matches.has(node.id);
      const isSel = state.selected === node;
      const isHov = state.hovered === node;
      const focused = !!(state.selected || state.hovered);
      ctx.globalAlpha = focused && !isPath && !isMatch && !isSel && !isHov ? 0.45 : 1;
      ctx.beginPath(); ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = palette[node.community % palette.length];
      ctx.fill();
      if (isPath || isMatch || isHov || isSel) {
        ctx.beginPath(); ctx.arc(node.x, node.y, r + 3 / globalScale, 0, 2 * Math.PI);
        ctx.strokeStyle = isPath ? '#ff2a2a' : isMatch ? '#ffb000' : '#eaeaea';
        ctx.lineWidth = 1.6 / globalScale; ctx.stroke();
      }
      const showLabel = state.labelIds.has(node.id) || isPath || isMatch || isHov || isSel;
      if (showLabel) {
        const fs = Math.max(9, Math.min(14, r * 1.15));
        const label = node.name.length > 30 ? node.name.slice(0, 27) + '…' : node.name;
        ctx.font = fs / globalScale + "px 'JetBrains Mono','IBM Plex Mono',Consolas,monospace";
        ctx.textAlign = 'center'; ctx.textBaseline = 'top';
        const labelY = node.y + r + 4 / globalScale;
        const width = ctx.measureText(label).width + 8 / globalScale;
        ctx.fillStyle = 'rgba(10,10,10,.82)';
        ctx.fillRect(node.x - width / 2, labelY - 2 / globalScale, width, fs / globalScale + 4 / globalScale);
        ctx.fillStyle = 'rgba(234,234,234,.96)';
        ctx.fillText(label, node.x, labelY);
      }
      ctx.globalAlpha = 1;
    })
    .linkCanvasObjectMode(function () { return 'replace'; })
    .linkCanvasObject(function (link, ctx, globalScale) {
      if (link.source.x == null || link.target.x == null) return;
      const inPath = state.pathLinks.has(link.id);
      const connected = !!(state.hovered || state.selected) && (link.source === state.hovered || link.target === state.hovered || link.source === state.selected || link.target === state.selected);
      const assertion = linkKind(link) === 'assertion';
      const curvature = state.linkCurvatures.get(link.id) || 0;
      const dx = link.target.x - link.source.x, dy = link.target.y - link.source.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const offset = curvature * Math.min(120, Math.max(56, distance));
      const controlX = (link.source.x + link.target.x) / 2 - dy / distance * offset;
      const controlY = (link.source.y + link.target.y) / 2 + dx / distance * offset;
      const alpha = inPath ? 1 : connected ? .96 : state.selected || state.hovered ? .25 : assertion ? .72 : .14 + linkConfidence(link) * .34;
      ctx.beginPath(); ctx.moveTo(link.source.x, link.source.y);
      if (curvature === 0) ctx.lineTo(link.target.x, link.target.y);
      else ctx.quadraticCurveTo(controlX, controlY, link.target.x, link.target.y);
      ctx.strokeStyle = inPath ? '#ff2a2a' : (tagColor[link.tag] || '#5c6370');
      ctx.lineWidth = (inPath ? 3 : connected ? 2.2 : Math.min(3.6, .72 + Math.log2((link.weight || 1) + 1) * .4)) / globalScale;
      ctx.globalAlpha = alpha;
      ctx.setLineDash(assertion ? [] : [4 / globalScale, 4 / globalScale]);
      ctx.stroke(); ctx.setLineDash([]);
      if (linkDirection(link) === 'directed') {
        const tangentX = link.target.x - (curvature === 0 ? link.source.x : controlX);
        const tangentY = link.target.y - (curvature === 0 ? link.source.y : controlY);
        const angle = Math.atan2(tangentY, tangentX), arrowSize = 5.5 / globalScale;
        const tipX = link.target.x - Math.cos(angle) * (radius(link.target) / globalScale + arrowSize * .35);
        const tipY = link.target.y - Math.sin(angle) * (radius(link.target) / globalScale + arrowSize * .35);
        ctx.beginPath(); ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX - Math.cos(angle - Math.PI / 6) * arrowSize, tipY - Math.sin(angle - Math.PI / 6) * arrowSize);
        ctx.lineTo(tipX - Math.cos(angle + Math.PI / 6) * arrowSize, tipY - Math.sin(angle + Math.PI / 6) * arrowSize);
        ctx.closePath(); ctx.fillStyle = inPath ? '#ff2a2a' : (tagColor[link.tag] || '#5c6370'); ctx.fill();
      }
      ctx.globalAlpha = 1;
    })
    .onNodeClick(function (node) { state.selected = node; const component = componentForNode(node.id, componentSummaries); if (component) { state.viewMode = 'component'; state.componentId = component.id; applyFilters(); } showPanel(node); })
    .onNodeHover(function (n) { state.hovered = n || null; })
    .cooldownTicks(220)
    .onEngineStop(function () {
      const charge = Graph.d3Force('charge');
      const linkForce = Graph.d3Force('link');
      const center = Graph.d3Force('center');
      if (!forcesConfigured) {
        if (charge && charge.strength) charge.strength(-280);
        if (linkForce && linkForce.distance) linkForce.distance(function (link) { return linkKind(link) === 'assertion' ? 98 : 72 + Math.max(0, 10 - Math.min(link.weight, 10)) * 2; });
        if (center && center.strength) center.strength(.65);
        Graph.d3Force('community', createCommunityForce());
        forcesConfigured = true;
        Graph.d3ReheatSimulation();
        return;
      }
      if (shouldFit) fitCurrentGraph();
    });

  window.addEventListener('resize', function () {
    Graph.width(el.clientWidth).height(el.clientHeight);
    shouldFit = true;
    Graph.d3ReheatSimulation();
  });

  function visibleLinks() {
    const out = [];
    links.forEach(function (l) {
      if (!state.tags[l.tag] && !(l.tag === 'both' && (state.tags.llm || state.tags.cooccurrence))) return;
      if (!state.relations[l.relation]) return;
      if (!state.kinds[linkKind(l)]) return;
      if (linkKind(l) === 'association' && l.weight < state.minWeight) return;
      if (linkConfidence(l) < state.minConfidence) return;
      out.push(l);
    });
    return out;
  }

  function updateViewControls() {
    const viewBox = document.getElementById('viewModes');
    const firstConnected = componentSummaries.find(function (component) { return component.edgeCount > 0; }) || componentSummaries[0];
    const active = state.viewMode === 'component' && state.componentId
      ? componentSummaries.find(function (component) { return component.id === state.componentId; })
      : state.viewMode === 'core' ? firstConnected : null;
    viewBox.innerHTML = '<div class="view-mode-buttons">'
      + '<button class="' + (state.viewMode === 'core' ? 'active' : 'ghost') + '" data-view="core">CORE NETWORK</button>'
      + '<button class="' + (state.viewMode === 'component' ? 'active' : 'ghost') + '" data-view="component">SELECTED COMPONENT</button>'
      + '<button class="' + (state.viewMode === 'all' ? 'active' : 'ghost') + '" data-view="all">ALL VISIBLE</button>'
      + '</div>';
    viewBox.querySelectorAll('[data-view]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.viewMode = button.dataset.view;
        if (state.viewMode === 'core' || state.viewMode === 'all') state.componentId = null;
        else if (!state.componentId && active) state.componentId = active.id;
        state.selected = null;
        applyFilters();
      });
    });

    const componentBox = document.getElementById('components');
    const connected = componentSummaries.filter(function (component) { return component.edgeCount > 0; });
    componentBox.innerHTML = '<p class="view-summary">' + (state.viewMode === 'all' ? currentNodes.length + ' concepts across visible components' : (active ? active.nodeCount + ' concepts · ' + active.edgeCount + ' links in view' : 'No connected components')) + '</p>'
      + '<div class="component-list">'
      + connected.slice(0, 8).map(function (component, index) {
        return '<button class="component-pick ' + (active && active.id === component.id ? 'selected' : '') + '" data-component="' + component.id + '"><span><b>#' + (index + 1) + '</b> ' + component.leadName + '</span><small>' + component.nodeCount + ' concepts · ' + component.edgeCount + ' links</small></button>';
      }).join('')
      + '</div>'
      + (connected.length > 8 ? '<p class="view-summary">+ ' + (connected.length - 8) + ' smaller components</p>' : '');
    componentBox.querySelectorAll('[data-component]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.viewMode = 'component';
        state.componentId = button.dataset.component;
        state.selected = null;
        applyFilters();
      });
    });
  }

  function applyFilters() {
    const filteredLinks = visibleLinks();
    componentSummaries = connectedComponents(filteredLinks);
    let active = state.viewMode === 'component' && state.componentId
      ? componentSummaries.find(function (component) { return component.id === state.componentId; })
      : null;
    if (state.viewMode !== 'all' && !active) active = componentSummaries.find(function (component) { return component.edgeCount > 0; }) || componentSummaries[0];
    if (state.viewMode === 'component' && active) state.componentId = active.id;

    const keep = active && state.viewMode !== 'all' ? new Set(active.nodeIds) : null;
    const baseNodes = keep ? nodes.filter(function (n) { return keep.has(n.id); }) : nodes.slice();
    currentNodes = baseNodes.map(function (node, index) {
      const angle = index / Math.max(1, baseNodes.length) * Math.PI * 2;
      const seedRadius = Math.max(45, Math.sqrt(Math.max(1, baseNodes.length)) * 40);
      return Object.assign({}, node, { x: Math.cos(angle) * seedRadius, y: Math.sin(angle) * seedRadius, vx: 0, vy: 0 });
    });
    currentLinks = (keep ? filteredLinks.filter(function (l) { return keep.has(endpointId(l.source)) && keep.has(endpointId(l.target)); }) : filteredLinks).map(function (link) { return Object.assign({}, link); });

    state.labelIds = new Set(currentNodes.slice().sort(function (a, b) {
      return (b.degree || 0) - (a.degree || 0) || (b.count || 0) - (a.count || 0) || a.name.localeCompare(b.name);
    }).slice(0, state.viewMode === 'all' ? 8 : 12).map(function (n) { return n.id; }));
    state.matches.forEach(function (id) { state.labelIds.add(id); });
    state.pathNodes.forEach(function (id) { state.labelIds.add(id); });
    if (state.selected) state.labelIds.add(state.selected.id);
    if (state.selected) {
      filteredLinks.forEach(function (l) {
        const s = endpointId(l.source), t = endpointId(l.target);
        if (s === state.selected.id) state.labelIds.add(t);
        if (t === state.selected.id) state.labelIds.add(s);
      });
    }

    const groups = {};
    currentLinks.forEach(function (l) {
      const key = [endpointId(l.source), endpointId(l.target)].sort().join('|');
      (groups[key] = groups[key] || []).push(l);
    });
    state.linkCurvatures = new Map();
    Object.keys(groups).forEach(function (key) {
      groups[key].forEach(function (l, index) {
        state.linkCurvatures.set(l.id, groups[key].length === 1 ? 0 : (index - (groups[key].length - 1) / 2) * .22);
      });
    });

    shouldFit = true;
    Graph.graphData({ nodes: currentNodes, links: currentLinks });
    document.getElementById('stat').textContent = currentNodes.length + ' NODES · ' + currentLinks.length + ' EDGES';
    const meta = document.getElementById('canvasMeta');
    meta.innerHTML = '<strong>' + currentLinks.length + ' visible links</strong><span>·</span><span>' + (state.viewMode === 'core' ? 'core network' : state.viewMode === 'all' ? 'all visible components' : 'selected component') + '</span>';
    updateViewControls();
  }

  function showPanel(node) {
    const p = document.getElementById('panel');
    let out = '<span class="kicker">NODE RECORD</span><h3>' + node.name + '</h3><div class="facts">'
      + '<dt>TYPE</dt><dd>' + node.type + '</dd>'
      + '<dt>DEGREE</dt><dd>' + node.degree + '</dd>'
      + '<dt>MENTIONS</dt><dd>' + node.count + '</dd>'
      + '<dt>COMMUNITY</dt><dd>' + node.community + '</dd>'
      + '<dt>SOURCES</dt><dd>' + (node.sources || []).join(', ') + '</dd></div>';
    if (node.snippet) out += '<div class="snippet"><strong>IN CONTEXT:</strong> ' + node.snippet + '</div>';
    let nbs = [];
    links.forEach(function (l) {
      const s = l.source.id || l.source, t = l.target.id || l.target;
      const arrow = linkDirection(l) === 'undirected' ? '↔' : '→';
      const meta = linkKind(l) + ' · ' + linkProvenance(l) + ' · W' + l.weight + ' · C' + Math.round(linkConfidence(l) * 100) + '%';
      const evidence = (l.evidence || []).map(function (item) { return item.text || ''; }).filter(Boolean).join(' || ') || l.snippet || '';
      if (s === node.id) nbs.push({ name: (byId[t] || {}).name || t, rel: l.relation, dir: arrow, meta: meta, evidence: evidence });
      else if (t === node.id) nbs.push({ name: (byId[s] || {}).name || s, rel: l.relation, dir: linkDirection(l) === 'undirected' ? '↔' : '←', meta: meta, evidence: evidence });
    });
    nbs.sort(function (a, b) { return a.name.localeCompare(b.name); });
    out += '<div class="neighbors"><strong>NEIGHBORS (' + nbs.length + ')</strong><ul>';
    nbs.slice(0, 40).forEach(function (nb) {
      out += '<li><span class="rel">' + nb.dir + ' ' + nb.rel + '</span> ' + nb.name + '<br/><span class="hint">' + nb.meta + '</span>'
        + (nb.evidence ? '<div class="snippet">' + nb.evidence + '</div>' : '') + '</li>';
    });
    if (!nbs.length) out += '<li class="hint">NO CONNECTIONS</li>';
    out += '</ul></div>';
    p.innerHTML = out;
    p.classList.add('open');
  }

  // search
  document.getElementById('search').addEventListener('input', function (e) {
    const q = e.target.value.trim().toLowerCase();
    state.matches = new Set();
    if (q) {
      nodes.forEach(function (n) { if (n.name.toLowerCase().indexOf(q) !== -1) state.matches.add(n.id); });
    }
    document.getElementById('searchhint').textContent = state.matches.size ? state.matches.size + ' MATCH(ES)' : '';
    if (q && state.matches.size) {
      const first = nodes.filter(function (n) { return state.matches.has(n.id); }).sort(function (a, b) { return (b.degree || 0) - (a.degree || 0) || (b.count || 0) - (a.count || 0); })[0];
      if (first && !currentNodes.some(function (n) { return n.id === first.id; })) {
        const component = componentForNode(first.id, componentSummaries);
        if (component) { state.viewMode = 'component'; state.componentId = component.id; applyFilters(); }
      }
      const visible = Graph.graphData().nodes.find(function (n) { return n.id === (first || {}).id && n.x != null; });
      if (visible) { Graph.centerAt(visible.x, visible.y, 500); Graph.zoom(Math.max(1.6, Graph.zoom()), 500); }
    }
  });

  // path
  const selA = document.getElementById('pathA'), selB = document.getElementById('pathB');
  nodes.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).forEach(function (n) {
    selA.add(new Option(n.name, n.id)); selB.add(new Option(n.name, n.id));
  });
  document.getElementById('pathGo').addEventListener('click', function () {
    const a = selA.value, b = selB.value;
    state.pathLinks = new Set(); state.pathNodes = new Set();
    document.getElementById('pathhint').textContent = '';
    if (!a || !b) return;
    const path = shortestPath(a, b);
    if (!path) { document.getElementById('pathhint').textContent = 'NO PATH FOUND.'; return; }
    const component = componentForNode(path[0], componentSummaries);
    if (component) { state.viewMode = 'component'; state.componentId = component.id; }
    for (let i = 0; i < path.length - 1; i++) {
      const found = links.find(function (l) {
        const s = endpointId(l.source), t = endpointId(l.target);
        return (s === path[i] && t === path[i + 1]) || (s === path[i + 1] && t === path[i]);
      });
      if (found) state.pathLinks.add(found.id);
    }
    path.forEach(function (id) { state.pathNodes.add(id); });
    applyFilters();
    document.getElementById('pathhint').textContent = path.length - 1 + ' HOP(S) — HIGHLIGHTED IN RED';
  });
  document.getElementById('pathClear').addEventListener('click', function () {
    state.pathLinks = new Set(); state.pathNodes = new Set();
    document.getElementById('pathhint').textContent = '';
  });

  function shortestPath(a, b) {
    if (a === b) return [a];
    const adj = {};
    links.forEach(function (l) {
      const s = endpointId(l.source), t = endpointId(l.target);
      (adj[s] = adj[s] || []).push(t); (adj[t] = adj[t] || []).push(s);
    });
    const prev = {}; prev[a] = null;
    const q = [a];
    while (q.length) {
      const cur = q.shift();
      if (cur === b) break;
      (adj[cur] || []).forEach(function (nxt) {
        if (!(nxt in prev)) { prev[nxt] = cur; q.push(nxt); }
      });
    }
    if (!(b in prev)) return null;
    const path = []; let cur = b;
    while (cur) { path.push(cur); cur = prev[cur]; }
    return path.reverse();
  }

  // filters UI
  const f = document.getElementById('filters');
  let html = '<div class="scroll">';
  ['llm', 'cooccurrence', 'both'].forEach(function (tag) {
    html += '<label class="row"><input type="checkbox" data-tag="' + tag + '" checked/> <span class="swatch" style="background:' + tagColor[tag] + '"></span> ' + TAG_LABEL[tag] + '</label>';
  });
  html += '</div><div class="hint">SEMANTICS</div><div class="scroll">';
  ['assertion', 'association'].forEach(function (kind) {
    state.kinds[kind] = true;
    html += '<label class="row"><input type="checkbox" data-kind="' + kind + '" checked/> ' + (kind === 'assertion' ? 'DIRECTED ASSERTION' : 'UNDIRECTED ASSOCIATION') + '</label>';
  });
  html += '</div><div class="hint">RELATIONS</div><div class="scroll">';
  Object.keys(state.relations).sort().forEach(function (rel) {
    html += '<label class="row"><input type="checkbox" data-rel="' + rel.replace(/"/g, '&quot;') + '" checked/> ' + rel + '</label>';
  });
  html += '</div><div class="hint">MIN WEIGHT: <span id="wv">1</span></div>';
  html += '<input id="weight" type="range" min="1" max="' + Math.max(1, links.reduce(function (m, l) { return Math.max(m, l.weight); }, 1)) + '" value="1" style="width:100%;accent-color:#e61919"/>';
  html += '<div class="hint">MIN CONFIDENCE: <span id="cv">0%</span></div>';
  html += '<input id="confidence" type="range" min="0" max="1" step="0.05" value="0" style="width:100%;accent-color:#e61919"/>';
  f.innerHTML = html;
  document.getElementById('weight').value = String(state.minWeight);
  document.getElementById('wv').textContent = String(state.minWeight);
  f.addEventListener('change', function (e) {
    if (e.target.dataset.tag) state.tags[e.target.dataset.tag] = e.target.checked;
    if (e.target.dataset.kind) state.kinds[e.target.dataset.kind] = e.target.checked;
    if (e.target.dataset.rel) state.relations[e.target.dataset.rel] = e.target.checked;
    if (e.target.id === 'weight') { state.minWeight = Number(e.target.value); document.getElementById('wv').textContent = e.target.value; }
    if (e.target.id === 'confidence') { state.minConfidence = Number(e.target.value); document.getElementById('cv').textContent = Math.round(state.minConfidence * 100) + '%'; }
    applyFilters();
  });

  // legend
  const communities = {};
  nodes.forEach(function (n) { communities[n.community] = true; });
  let lh = '';
  Object.keys(communities).map(Number).sort(function (a, b) { return a - b; }).forEach(function (c) {
    lh += '<div class="row" style="display:flex;align-items:center;gap:8px;font-size:10px;padding:2px 0;text-transform:uppercase">'
      + '<span class="swatch" style="background:' + palette[c % palette.length] + '"></span> COMM ' + c + '</div>';
  });
  document.getElementById('legend').innerHTML = lh || '<span class="hint">NO COMMUNITIES</span>';

  document.getElementById('fitVisible').addEventListener('click', function () {
    fitCurrentGraph();
  });
  document.getElementById('fitCore').addEventListener('click', function () {
    state.viewMode = 'core'; state.componentId = null; state.selected = null;
    applyFilters();
  });
  document.getElementById('resetMap').addEventListener('click', function () {
    state.viewMode = 'core'; state.componentId = null; state.selected = null;
    state.pathLinks = new Set(); state.pathNodes = new Set(); state.matches = new Set();
    document.getElementById('search').value = '';
    document.getElementById('searchhint').textContent = '';
    document.getElementById('pathhint').textContent = '';
    applyFilters();
  });

  applyFilters();
})();
</script>
</body>
</html>
"""


def render_html_export(graph: dict[str, Any]) -> str:
    """Render a self-contained interactive HTML page for *graph*."""
    title = graph.get("document", {}).get("name", "Document")
    graph_json = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    # The JSON lands inside a <script> block. Node names, snippets, and evidence
    # come from user documents, so a literal "</" (e.g. "</script>") would
    # terminate the script element early. Escaping "<" as \u003c is equivalent
    # for both the JSON literal and the JS engine that evaluates it.
    graph_json = graph_json.replace("<", "\\u003c")
    return (
        _TEMPLATE.replace("__TITLE__", _escape_html(title))
        .replace("__GRAPH_JSON__", graph_json)
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
