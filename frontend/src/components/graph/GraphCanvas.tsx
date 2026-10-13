'use client';
import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
}

const TYPE_COLOR: Record<string, string> = {
  Employee: '#3b82f6',
  Project: '#10b981',
  Meeting: '#f59e0b',
  Document: '#a78bfa',
  Unknown: '#6b7280',
};

const TYPE_BADGE: Record<string, string> = {
  Employee: 'Person',
  Project: 'Body / initiative',
  Meeting: 'Meeting',
  Document: 'Document',
};

const REPULSION = 4000;
const SPRING_K = 0.04;
const SPRING_REST = 130;
const DAMPING = 0.84;
const GRAVITY = 0.0015;

export default function GraphCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<'loading' | 'empty' | 'error' | 'ready'>('loading');

  useEffect(() => {
    let animId = 0;
    let onResize: (() => void) | null = null;

    apiFetch('/api/v1/graph/data')
      .then((r) => r.json())
      .then((data: { nodes: { id: string; name: string; type: string }[]; links: GraphLink[] }) => {
        const rawNodes = data.nodes ?? [];
        const rawLinks = data.links ?? [];

        if (rawNodes.length === 0) {
          setStatus('empty');
          return;
        }
        setStatus('ready');

        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let W = canvas.offsetWidth || 900;
        let H = canvas.offsetHeight || 600;
        canvas.width = W;
        canvas.height = H;

        const handleResize = () => {
          if (!canvasRef.current) return;
          W = canvasRef.current.offsetWidth || 900;
          H = canvasRef.current.offsetHeight || 600;
          canvasRef.current.width = W;
          canvasRef.current.height = H;
        };
        onResize = handleResize;
        window.addEventListener('resize', handleResize);

        // Initialise node positions in a circle to avoid initial clustering
        const nodes: GraphNode[] = rawNodes.map((n, i) => {
          const angle = (2 * Math.PI * i) / rawNodes.length;
          return {
            ...n,
            x: W / 2 + Math.cos(angle) * (Math.min(W, H) * 0.3),
            y: H / 2 + Math.sin(angle) * (Math.min(W, H) * 0.3),
            vx: 0,
            vy: 0,
          };
        });

        const nodeMap = new Map(nodes.map((n) => [n.id, n]));

        const simulate = () => {
          // Repulsion between every node pair (O(n²) – fine for <200 nodes)
          for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
              const dx = nodes[j].x - nodes[i].x || 0.1;
              const dy = nodes[j].y - nodes[i].y || 0.1;
              const dist2 = dx * dx + dy * dy;
              const dist = Math.sqrt(dist2) || 0.1;
              const force = REPULSION / dist2;
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;
              nodes[i].vx -= fx;
              nodes[i].vy -= fy;
              nodes[j].vx += fx;
              nodes[j].vy += fy;
            }
          }

          // Spring attraction along edges
          for (const link of rawLinks) {
            const src = nodeMap.get(link.source);
            const tgt = nodeMap.get(link.target);
            if (!src || !tgt) continue;
            const dx = tgt.x - src.x;
            const dy = tgt.y - src.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 0.1;
            const force = SPRING_K * (dist - SPRING_REST);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            src.vx += fx;
            src.vy += fy;
            tgt.vx -= fx;
            tgt.vy -= fy;
          }

          // Centre gravity + damping + integrate
          for (const n of nodes) {
            n.vx += (W / 2 - n.x) * GRAVITY;
            n.vy += (H / 2 - n.y) * GRAVITY;
            n.vx *= DAMPING;
            n.vy *= DAMPING;
            n.x = Math.max(40, Math.min(W - 40, n.x + n.vx));
            n.y = Math.max(40, Math.min(H - 40, n.y + n.vy));
          }
        };

        const draw = () => {
          ctx.clearRect(0, 0, W, H);
          ctx.fillStyle = '#0d1117';
          ctx.fillRect(0, 0, W, H);

          // Edges
          for (const link of rawLinks) {
            const src = nodeMap.get(link.source);
            const tgt = nodeMap.get(link.target);
            if (!src || !tgt) continue;
            ctx.beginPath();
            ctx.moveTo(src.x, src.y);
            ctx.lineTo(tgt.x, tgt.y);
            ctx.strokeStyle = 'rgba(99,102,241,0.35)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Edge label
            const mx = (src.x + tgt.x) / 2;
            const my = (src.y + tgt.y) / 2;
            ctx.fillStyle = 'rgba(148,163,184,0.6)';
            ctx.font = '9px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(link.type, mx, my);
          }

          // Nodes
          for (const n of nodes) {
            const color = TYPE_COLOR[n.type] ?? TYPE_COLOR.Unknown;
            const radius = 20;

            // Glow
            const grd = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, radius * 2);
            grd.addColorStop(0, color + '44');
            grd.addColorStop(1, 'transparent');
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius * 2, 0, 2 * Math.PI);
            ctx.fillStyle = grd;
            ctx.fill();

            // Circle
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = color + '22';
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            const label = n.name.length > 14 ? n.name.slice(0, 13) + '…' : n.name;
            ctx.fillStyle = '#f1f5f9';
            ctx.font = '11px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(label, n.x, n.y + radius + 14);

            // Type badge
            const badge = TYPE_BADGE[n.type] ?? n.type;
            ctx.fillStyle = color + 'cc';
            ctx.font = '9px Inter, sans-serif';
            ctx.fillText(badge, n.x, n.y + radius + 25);
          }
        };

        let frame = 0;
        const loop = () => {
          simulate();
          if (frame % 2 === 0) draw(); // draw every other frame to ease GPU load
          frame++;
          animId = requestAnimationFrame(loop);
        };
        loop();
      })
      .catch(() => setStatus('error'));

    return () => {
      if (animId) cancelAnimationFrame(animId);
      if (onResize) window.removeEventListener('resize', onResize);
    };
  }, []);

  if (status === 'loading') {
    return (
      <div className="glass-panel p-12 text-center text-slate-400 animate-pulse">
        Loading institutional relationship graph…
      </div>
    );
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
          <a href="/sources" className="text-blue-400 hover:underline">
            Document Repositories
          </a>{' '}
          — faculty, deans, and committee entities will appear here automatically following NER indexing.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel overflow-hidden">
      <canvas
        ref={canvasRef}
        className="w-full h-[360px] sm:h-[460px] md:h-[540px] lg:h-[600px] block"
        aria-label="Force-directed organizational relationship graph"
        role="img"
      />
    </div>
  );
}
