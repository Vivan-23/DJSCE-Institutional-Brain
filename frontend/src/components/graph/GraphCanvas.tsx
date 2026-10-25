'use client';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Core, EdgeSingular, ElementDefinition, NodeSingular } from 'cytoscape';
import { apiFetch } from '@/lib/api';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  department: string | null;
  visibility: string | null;
  degree: number;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  truncated?: boolean;
}

const TYPES: { key: string; label: string; color: string }[] = [
  { key: 'Employee', label: 'People', color: '#3b82f6' },
  { key: 'Project', label: 'Committees & departments', color: '#10b981' },
  { key: 'Meeting', label: 'Meetings', color: '#f59e0b' },
  { key: 'Document', label: 'Documents', color: '#a78bfa' },
];
const COLOR: Record<string, string> = Object.fromEntries(TYPES.map((t) => [t.key, t.color]));
const LABEL: Record<string, string> = { Employee: 'Person', Project: 'Committee / department', Meeting: 'Meeting', Document: 'Document' };
const EDGE_COLOR: Record<string, string> = { ATTENDED: '#f59e0b', MENTIONS: '#6366f1', WORKS_ON: '#10b981' };

/** A node linked to more than this share of the visible nodes is a "hub" (e.g. the college itself). */
const HUB_SHARE = 0.25;

function elements(data: GraphData): ElementDefinition[] {
  return [
    ...data.nodes.map((n) => ({ group: 'nodes' as const, data: { ...n, label: n.name } })),
    ...data.links.map((l, i) => ({
      group: 'edges' as const,
      data: { id: `e${i}-${l.source}-${l.target}-${l.type}`, source: l.source, target: l.target, type: l.type },
    })),
  ];
}

export default function GraphCanvas() {
  const boxRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [status, setStatus] = useState<'loading' | 'empty' | 'error' | 'ready'>('loading');
  const [data, setData] = useState<GraphData | null>(null);
  const [shown, setShown] = useState<Record<string, boolean>>({ Employee: true, Project: true, Meeting: true, Document: false });
  const [hideHubs, setHideHubs] = useState(true);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [neighbours, setNeighbours] = useState<GraphNode[]>([]);
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    apiFetch('/api/v1/graph/data')
      .then((r) => r.json())
      .then((d: GraphData) => {
        if (!d.nodes?.length) {
          setStatus('empty');
          return;
        }
        setData(d);
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  }, []);

  const hubs = useMemo(() => {
    if (!data) return new Set<string>();
    const limit = Math.max(8, data.nodes.length * HUB_SHARE);
    return new Set(data.nodes.filter((n) => n.degree > limit).map((n) => n.id));
  }, [data]);

  /** Focus a node: keep it and its direct connections bright, fade everything else. */
  const focus = useCallback((node: NodeSingular | null) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass('faded focus');
    if (!node) {
      setSelected(null);
      setNeighbours([]);
      return;
    }
    const hood = node.closedNeighborhood();
    cy.elements().not(hood).addClass('faded');
    node.addClass('focus');
    setSelected(node.data() as GraphNode);
    setNeighbours(
      node
        .neighborhood('node')
        .map((n) => n.data() as GraphNode)
        .sort((a, b) => b.degree - a.degree),
    );
    cy.animate({
      fit: { eles: hood, padding: 80 },
      duration: 300,
      // A node with few connections would otherwise fill the screen.
      complete: () => {
        if (cy.zoom() > 1.4) cy.zoom({ level: 1.4, position: node.position() });
      },
    });
  }, []);

  // Build the Cytoscape instance once data has arrived and the container is mounted.
  useEffect(() => {
    if (!data || !boxRef.current) return;
    let destroyed = false;
    import('cytoscape').then(({ default: cytoscape }) => {
      if (destroyed || !boxRef.current) return;
      const maxDeg = Math.max(1, ...data.nodes.map((n) => n.degree));
      const cy = cytoscape({
        container: boxRef.current,
        elements: elements(data),
        minZoom: 0.15,
        maxZoom: 3,
        wheelSensitivity: 0.25,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': (n: NodeSingular) => COLOR[n.data('type')] ?? '#6b7280',
              width: (n: NodeSingular) => 14 + 34 * Math.sqrt(n.data('degree') / maxDeg),
              height: (n: NodeSingular) => 14 + 34 * Math.sqrt(n.data('degree') / maxDeg),
              label: 'data(label)',
              color: '#e2e8f0',
              'font-size': (n: NodeSingular) => 9 + 5 * Math.sqrt(n.data('degree') / maxDeg),
              'min-zoomed-font-size': 7, // labels appear as you zoom in, so small nodes don't clutter
              'text-valign': 'bottom',
              'text-margin-y': 4,
              'text-wrap': 'ellipsis',
              'text-max-width': '120px',
              'text-outline-color': '#0d1117',
              'text-outline-width': 2,
              'border-width': 1.5,
              'border-color': '#0d1117',
            },
          },
          {
            selector: 'edge',
            style: {
              width: 1.2,
              'line-color': (e) => EDGE_COLOR[e.data('type')] ?? '#64748b',
              opacity: 0.45,
              'curve-style': 'haystack',
            },
          },
          { selector: '.faded', style: { opacity: 0.08, 'text-opacity': 0 } },
          { selector: 'node.focus', style: { 'border-color': '#f8fafc', 'border-width': 3 } },
          { selector: 'node.match', style: { 'border-color': '#facc15', 'border-width': 3 } },
        ],
      });
      cy.on('tap', 'node', (evt) => focus(evt.target as NodeSingular));
      cy.on('tap', (evt) => {
        if (evt.target === cy) focus(null);
      });
      cyRef.current = cy;
      (window as unknown as { __cy?: Core }).__cy = cy; // lets automated UI checks drive the graph
      window.dispatchEvent(new Event('graph-ready'));
    });
    return () => {
      destroyed = true;
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [data, focus]);

  // Apply type / hub filters, then lay out what's visible.
  const applyFilters = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.nodes().forEach((n) => {
        const hidden = !shown[n.data('type')] || (hideHubs && hubs.has(n.id()));
        n.style('display', hidden ? 'none' : 'element');
      });
    });
    // Nodes left with no visible connection add noise; hide them too (after the batch, so
    // visibility reflects the filters just applied).
    cy.batch(() => {
      cy.nodes().forEach((n) => {
        if (n.style('display') === 'none') return;
        const linked = n
          .connectedEdges()
          .toArray()
          .some((e) => (e as EdgeSingular).source().visible() && (e as EdgeSingular).target().visible());
        if (!linked) n.style('display', 'none');
      });
    });
    const visible = cy.elements(':visible');
    setVisibleCount(cy.nodes(':visible').length);
    visible
      .layout({
        name: 'cose',
        animate: false,
        nodeRepulsion: () => 40000,
        idealEdgeLength: () => 140,
        nodeOverlap: 40,
        gravity: 0.15,
        numIter: 2500,
        padding: 40,
        randomize: true,
      })
      .run();
  }, [shown, hideHubs, hubs]);

  useEffect(() => {
    const run = () => applyFilters();
    if (cyRef.current) run();
    window.addEventListener('graph-ready', run);
    return () => window.removeEventListener('graph-ready', run);
  }, [applyFilters]);

  const search = (e: React.FormEvent) => {
    e.preventDefault();
    const cy = cyRef.current;
    if (!cy || !query.trim()) return;
    cy.nodes().removeClass('match');
    const q = query.trim().toLowerCase();
    const hits = cy.nodes().filter((n) => String(n.data('name')).toLowerCase().includes(q));
    if (hits.length === 0) return;
    hits.forEach((n) => {
      n.style('display', 'element'); // a search result is shown even if its type is filtered out
    });
    hits.addClass('match');
    focus(hits[0] as NodeSingular);
  };

  /** Pull the node's full neighbourhood from the server (for graphs too big to load at once). */
  const expand = async () => {
    const cy = cyRef.current;
    if (!cy || !selected) return;
    const res = await apiFetch(`/api/v1/graph/neighbors/${encodeURIComponent(selected.id)}?depth=1`);
    if (!res.ok) return;
    const hood: GraphData = await res.json();
    const fresh = elements(hood).filter((el) => {
      const id = el.data.id as string | undefined;
      if (el.group === 'nodes') return id ? cy.getElementById(id).empty() : false;
      return !cy.edges().some(
        (e) => e.data('source') === el.data.source && e.data('target') === el.data.target && e.data('type') === el.data.type,
      );
    });
    cy.add(fresh);
    const node = cy.getElementById(selected.id);
    node.closedNeighborhood().style('display', 'element');
    focus(node as NodeSingular);
  };

  if (status === 'loading') {
    return <div className="glass-panel p-12 text-center text-slate-400 animate-pulse">Loading institutional relationship graph…</div>;
  }
  if (status === 'error') {
    return (
      <div className="glass-panel p-12 text-center text-rose-400">
        Failed to load graph data. Ensure the backend and Neo4j database are running.
      </div>
    );
  }
  if (status === 'empty') {
    return (
      <div className="glass-panel p-12 text-center space-y-2">
        <p className="text-slate-300 font-medium">No institutional relationships mapped yet</p>
        <p className="text-slate-400 text-xs max-w-md mx-auto">
          Upload committee minutes or departmental circulars in{' '}
          <a href="/sources" className="text-blue-400 hover:underline">Document Repositories</a>; people, meetings and
          committees appear here automatically after indexing.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="glass-panel p-3 flex flex-wrap items-center gap-2 text-xs">
        <form onSubmit={search} className="flex gap-1.5">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find a person, committee, meeting…"
            aria-label="Search the graph"
            className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1 text-xs text-slate-100 w-56 focus:outline-none focus:border-blue-500"
          />
          <button type="submit" className="px-2.5 py-1 rounded border border-slate-700 text-slate-200 hover:border-blue-500/60 cursor-pointer">
            Find
          </button>
        </form>
        <span className="mx-1 h-4 w-px bg-slate-700" aria-hidden />
        {TYPES.map((t) => (
          <label key={t.key} className="flex items-center gap-1.5 cursor-pointer text-slate-300">
            <input type="checkbox" checked={shown[t.key]} onChange={(e) => setShown({ ...shown, [t.key]: e.target.checked })} />
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: t.color }} />
            {t.label}
          </label>
        ))}
        <label className="flex items-center gap-1.5 cursor-pointer text-slate-300" title="Nodes linked to a large share of the graph, such as the college itself">
          <input type="checkbox" checked={hideHubs} onChange={(e) => setHideHubs(e.target.checked)} />
          Hide hubs{hubs.size ? ` (${hubs.size})` : ''}
        </label>
        <button
          type="button"
          onClick={() => {
            focus(null);
            cyRef.current?.animate({ fit: { eles: cyRef.current.elements(':visible'), padding: 30 }, duration: 300 });
          }}
          className="ml-auto px-2.5 py-1 rounded border border-slate-700 text-slate-200 hover:border-blue-500/60 cursor-pointer"
        >
          Reset view
        </button>
      </div>

      {data?.truncated && (
        <p className="text-[0.75rem] text-amber-300/90">
          The graph is larger than the display limit, so some links are not drawn. Search for a node and use “Show all its
          connections” to load its full neighbourhood.
        </p>
      )}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_18rem] gap-3">
        <div className="glass-panel overflow-hidden relative">
          <div
            ref={boxRef}
            className="w-full h-[420px] sm:h-[520px] lg:h-[620px] bg-[#0d1117]"
            role="img"
            aria-label="Knowledge graph of people, committees, meetings and documents"
          />
          <p className="absolute bottom-2 left-3 text-[0.6875rem] text-slate-500 pointer-events-none">
            {visibleCount} nodes shown · scroll to zoom · drag to pan · click a node to focus
          </p>
        </div>

        <aside className="glass-panel p-3 text-xs space-y-2 max-h-[620px] overflow-y-auto" aria-label="Selected node">
          {!selected ? (
            <div className="text-slate-400 space-y-2">
              <p className="text-slate-200 font-medium">Click a node to focus it.</p>
              <p>Only it and its direct connections stay bright; its connections are listed here.</p>
              <p>Bigger nodes have more connections. Labels of small nodes appear as you zoom in.</p>
              <p>
                Lines: <span style={{ color: EDGE_COLOR.ATTENDED }}>orange</span> = attended a meeting,{' '}
                <span style={{ color: EDGE_COLOR.MENTIONS }}>indigo</span> = mentioned in a document or meeting.
              </p>
            </div>
          ) : (
            <>
              <div>
                <p className="text-sm font-semibold text-slate-100 break-words">{selected.name}</p>
                <p className="text-slate-400">
                  {LABEL[selected.type] ?? selected.type}
                  {selected.department && selected.department !== 'all' ? ` · ${selected.department}` : ''}
                  {selected.visibility ? ` · ${selected.visibility}` : ''} · {selected.degree} connection
                  {selected.degree === 1 ? '' : 's'}
                </p>
              </div>
              <button type="button" onClick={expand} className="w-full px-2 py-1 rounded border border-slate-700 text-slate-200 hover:border-blue-500/60 cursor-pointer">
                Show all its connections
              </button>
              <ul className="space-y-1">
                {neighbours.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => {
                        const node = cyRef.current?.getElementById(n.id);
                        if (node && node.nonempty()) {
                          node.style('display', 'element');
                          focus(node as NodeSingular);
                        }
                      }}
                      className="w-full text-left flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-800/70 cursor-pointer"
                    >
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLOR[n.type] ?? '#6b7280' }} />
                      <span className="text-slate-200 truncate">{n.name}</span>
                      <span className="ml-auto text-slate-500">{n.degree}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
