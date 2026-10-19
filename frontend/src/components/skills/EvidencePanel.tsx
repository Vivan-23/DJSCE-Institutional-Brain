'use client';
import React, { useMemo, useState } from 'react';

export interface Citation {
  citation_id: string;
  fragment_id: string;
  source_type: string | null;
  source_ref?: string | null;
  element?: string | null;
  content: string | null;
}

interface EvidencePanelProps {
  citations: Citation[];
}

export interface DeduplicatedEvidence {
  id: string;
  normKey: string;
  displayExcerpt: string;
  rawExcerpt: string;
  citations: Citation[];
  sourceTypes: string[];
  sourceRefs: string[];
  elements: string[];
  inferredCategory: string;
  isSopClause: boolean;
}

interface SourceGroup {
  key: string;
  label: string;
  description: string;
  badgeStyle: string;
  items: DeduplicatedEvidence[];
  totalReferences: number;
}

/**
 * Normalizes excerpt text for conservative deduplication.
 * Strips whitespace variance, line ending variance, and purely display-oriented prefixes.
 */
function normalizeContent(raw: string | null): { normKey: string; displayText: string; isSopClause: boolean } {
  if (!raw) return { normKey: '', displayText: '', isSopClause: false };

  // Standardize carriage returns
  let clean = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();

  // Strip display-only bracketed prefixes like [transcript]: or [checkin]:
  clean = clean.replace(/^\[(?:transcript|checkin|doc|document|evidence|meeting|slack|email|ticket)\]:?\s*/i, '');

  // Detect if this is an extracted SOP section header
  const isSopClause = /^#{1,3}\s+(?:\d+\.|\b(?:Trigger|Preconditions|Steps|Execution|Decision|Guardrails|Escalation|Integrity|Standard Operating Procedure)\b)/i.test(clean);

  // For normalization comparison: collapse internal whitespace and lower-case
  const normKey = clean.toLowerCase().replace(/\s+/g, ' ').trim();

  return { normKey, displayText: clean, isSopClause };
}

/**
 * Determines an honest category label based purely on available metadata and excerpt structure.
 */
function categorizeEvidence(
  sourceType?: string | null,
  isSopClause: boolean = false,
): { key: string; label: string; description: string; badgeStyle: string } {
  if (isSopClause) {
    return {
      key: 'sop_section',
      label: 'Synthesized SOP Clauses & Bylaws',
      description: 'Structured procedural clauses extracted directly from regulatory references or previous drafts.',
      badgeStyle: 'bg-purple-500/15 border-purple-500/30 text-purple-300',
    };
  }

  const st = (sourceType || '').toLowerCase();
  if (st === 'transcript') {
    return {
      key: 'transcript',
      label: 'Meeting Transcripts & Deliberations',
      description: 'Verbatim spoken statements and committee decisions recorded in institutional meeting transcripts.',
      badgeStyle: 'bg-blue-500/15 border-blue-500/30 text-blue-300',
    };
  }

  if (st === 'doc' || st === 'document') {
    return {
      key: 'doc',
      label: 'Institutional Documents & Guidelines',
      description: 'Excerpts ingested from official academic council circulars, syllabus specs, and audit guidelines.',
      badgeStyle: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300',
    };
  }

  if (st === 'checkin') {
    return {
      key: 'checkin',
      label: 'Faculty Desk Updates & Check-ins',
      description: 'Operational status reports and readiness confirmations received from departmental faculty.',
      badgeStyle: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
    };
  }

  return {
    key: 'unattributed',
    label: 'Unattributed Source Excerpts',
    description: 'Evidence fragments recorded in the knowledge base without an explicit source record type.',
    badgeStyle: 'bg-slate-700/20 border-slate-600/40 text-slate-400',
  };
}

export default function EvidencePanel({ citations }: EvidencePanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [expandedExcerpts, setExpandedExcerpts] = useState<Record<string, boolean>>({});
  const [inspectedProvenance, setInspectedProvenance] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Group and deduplicate citations conservatively
  const { groups, stats } = useMemo(() => {
    if (!citations || citations.length === 0) {
      return {
        groups: [] as SourceGroup[],
        deduplicatedList: [] as DeduplicatedEvidence[],
        stats: { totalCitations: 0, uniqueExcerpts: 0, duplicateCount: 0, categoryCount: 0 },
      };
    }

    const itemMap = new Map<string, DeduplicatedEvidence>();

    citations.forEach((cit) => {
      const raw = cit.content ?? '';
      const { normKey, displayText, isSopClause } = normalizeContent(raw);
      if (!normKey) return;

      const existing = itemMap.get(normKey);
      if (existing) {
        existing.citations.push(cit);
        if (cit.source_type && !existing.sourceTypes.includes(cit.source_type)) {
          existing.sourceTypes.push(cit.source_type);
        }
        if (cit.source_ref && !existing.sourceRefs.includes(cit.source_ref)) {
          existing.sourceRefs.push(cit.source_ref);
        }
        if (cit.element && !existing.elements.includes(cit.element)) {
          existing.elements.push(cit.element);
        }
      } else {
        const catInfo = categorizeEvidence(cit.source_type, isSopClause);
        itemMap.set(normKey, {
          id: cit.citation_id || `ev-${itemMap.size + 1}`,
          normKey,
          displayExcerpt: displayText,
          rawExcerpt: raw,
          citations: [cit],
          sourceTypes: cit.source_type ? [cit.source_type] : [],
          sourceRefs: cit.source_ref ? [cit.source_ref] : [],
          elements: cit.element ? [cit.element] : [],
          inferredCategory: catInfo.key,
          isSopClause,
        });
      }
    });

    const deduplicatedList = Array.from(itemMap.values());

    // Group into categories
    const groupMap = new Map<string, SourceGroup>();

    deduplicatedList.forEach((item) => {
      const firstCit = item.citations[0];
      const catInfo = categorizeEvidence(firstCit.source_type, item.isSopClause);

      if (!groupMap.has(catInfo.key)) {
        groupMap.set(catInfo.key, {
          key: catInfo.key,
          label: catInfo.label,
          description: catInfo.description,
          badgeStyle: catInfo.badgeStyle,
          items: [],
          totalReferences: 0,
        });
      }

      const g = groupMap.get(catInfo.key)!;
      g.items.push(item);
      g.totalReferences += item.citations.length;
    });

    const groups = Array.from(groupMap.values()).sort((a, b) => b.items.length - a.items.length);

    const totalCitations = citations.length;
    const uniqueExcerpts = deduplicatedList.length;
    const duplicateCount = Math.max(0, totalCitations - uniqueExcerpts);
    const categoryCount = groups.length;

    return {
      groups,
      deduplicatedList,
      stats: { totalCitations, uniqueExcerpts, duplicateCount, categoryCount },
    };
  }, [citations]);

  // Filter items by search query and category
  const filteredGroups = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();

    return groups
      .map((group) => {
        if (selectedCategory !== 'all' && group.key !== selectedCategory) {
          return null;
        }

        const matchingItems = group.items.filter((item) => {
          if (!q) return true;
          return (
            item.displayExcerpt.toLowerCase().includes(q) ||
            item.citations.some((c) =>
              c.citation_id.toLowerCase().includes(q) ||
              c.fragment_id.toLowerCase().includes(q) ||
              (c.source_ref && c.source_ref.toLowerCase().includes(q))
            )
          );
        });

        if (matchingItems.length === 0) return null;

        const totalRefs = matchingItems.reduce((acc, it) => acc + it.citations.length, 0);

        return {
          ...group,
          items: matchingItems,
          totalReferences: totalRefs,
        };
      })
      .filter((g): g is SourceGroup => g !== null);
  }, [groups, searchQuery, selectedCategory]);

  const totalFilteredExcerpts = filteredGroups.reduce((acc, g) => acc + g.items.length, 0);

  const toggleExcerptExpand = (id: string) => {
    setExpandedExcerpts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleProvenance = (id: string) => {
    setInspectedProvenance((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopy = (id: string, text: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
      });
    }
  };

  if (!citations || citations.length === 0) {
    return (
      <div className="pt-3 border-t border-slate-800/80 text-xs text-slate-500 italic">
        No recorded source citations for this procedure.
      </div>
    );
  }

  return (
    <section className="pt-3 border-t border-slate-800/80 space-y-4" aria-label="Evidence and Source Documents">
      {/* Summary Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-slate-900/50 border border-slate-800 rounded-lg p-3.5">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-xs font-semibold text-slate-200">
              Evidence &amp; Source Documents
            </h3>
            <span className="text-[12px] px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 font-mono font-medium">
              {stats.uniqueExcerpts} unique {stats.uniqueExcerpts === 1 ? 'excerpt' : 'excerpts'}
            </span>
            {stats.duplicateCount > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300 font-medium">
                {stats.duplicateCount} duplicate {stats.duplicateCount === 1 ? 'ref' : 'refs'} grouped
              </span>
            )}
            <span className="text-[11px] text-slate-500">
              ({stats.totalCitations} raw {stats.totalCitations === 1 ? 'citation' : 'citations'} total)
            </span>
          </div>
          <p className="text-[12px] text-slate-400">
            Explore the verified source excerpts used to synthesize this procedure.
          </p>
        </div>

        <button
          onClick={() => setIsExpanded((prev) => !prev)}
          className="text-xs self-start sm:self-center px-3 py-1.5 rounded bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/40 text-blue-300 font-medium transition-colors cursor-pointer shrink-0 flex items-center gap-1.5"
          aria-expanded={isExpanded}
        >
          <span>{isExpanded ? 'Hide Evidence' : 'View Evidence'}</span>
          <span className={`text-[11px] transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
            ▼
          </span>
        </button>
      </div>

      {/* Expanded Content Panel */}
      {isExpanded && (
        <div className="space-y-4 pt-1">
          {/* Controls: Search and Category Filter */}
          <div className="flex flex-col sm:flex-row gap-2.5 items-stretch sm:items-center justify-between text-xs">
            <div className="relative flex-1 max-w-sm">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search evidence text or ID…"
                className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-hidden focus:border-blue-500/60"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                  title="Clear search"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Category Filter Pills */}
            <div className="flex flex-wrap gap-1.5 items-center">
              <button
                onClick={() => setSelectedCategory('all')}
                className={`text-[12px] px-2.5 py-1 rounded-full border transition-colors cursor-pointer ${
                  selectedCategory === 'all'
                    ? 'bg-blue-500/20 border-blue-500/40 text-blue-300 font-medium'
                    : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`}
              >
                All Categories ({stats.uniqueExcerpts})
              </button>
              {groups.map((g) => (
                <button
                  key={g.key}
                  onClick={() => setSelectedCategory(g.key)}
                  className={`text-[12px] px-2.5 py-1 rounded-full border transition-colors cursor-pointer ${
                    selectedCategory === g.key
                      ? 'bg-blue-500/20 border-blue-500/40 text-blue-300 font-medium'
                      : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  {g.label.split('&')[0].trim()} ({g.items.length})
                </button>
              ))}
            </div>
          </div>

          {/* Results Summary if filtered */}
          {(searchQuery || selectedCategory !== 'all') && (
            <div className="text-[12px] text-slate-400 flex items-center justify-between">
              <span>
                Showing {totalFilteredExcerpts} of {stats.uniqueExcerpts} unique evidence excerpts
              </span>
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedCategory('all');
                }}
                className="text-blue-400 hover:underline cursor-pointer"
              >
                Reset filters
              </button>
            </div>
          )}

          {/* Grouped Evidence Listings */}
          {filteredGroups.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 rounded bg-slate-900/40 border border-slate-800">
              No evidence excerpts matched your filter criteria.
            </div>
          ) : (
            <div className="space-y-4">
              {filteredGroups.map((group) => (
                <div key={group.key} className="space-y-2">
                  {/* Source Group Header */}
                  <div className="flex items-center justify-between pb-1 border-b border-slate-800">
                    <div className="flex items-center gap-2">
                      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${group.badgeStyle}`}>
                        {group.label}
                      </span>
                      <span className="text-[12px] text-slate-400">
                        {group.items.length} {group.items.length === 1 ? 'excerpt' : 'excerpts'}
                        {group.totalReferences > group.items.length && (
                          <span className="text-slate-500 ml-1">
                            ({group.totalReferences} references)
                          </span>
                        )}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-500 hidden sm:inline">
                      {group.description}
                    </span>
                  </div>

                  {/* Excerpt Cards */}
                  <div className="space-y-2">
                    {group.items.map((item) => {
                      const isLong = item.displayExcerpt.length > 240 || item.displayExcerpt.includes('\n');
                      const isOpen = expandedExcerpts[item.id] ?? false;
                      const isProvOpen = inspectedProvenance[item.id] ?? false;
                      const hasDuplicates = item.citations.length > 1;

                      return (
                        <div
                          key={item.id}
                          className="p-3 sm:p-3.5 rounded-md bg-slate-900/70 border border-slate-800 hover:border-slate-700/80 transition-colors text-xs space-y-2"
                        >
                          {/* Excerpt Meta Header */}
                          <div className="flex items-start justify-between gap-2 flex-wrap">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {/* Source Type Badge */}
                              <span className="text-[11px] font-medium text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded">
                                {item.sourceTypes.join(', ') || 'Stored Record'}
                              </span>

                              {/* Multi-reference indicator */}
                              {hasDuplicates && (
                                <span className="text-[11px] font-medium text-blue-300 bg-blue-500/15 border border-blue-500/30 px-1.5 py-0.5 rounded">
                                  {item.citations.length} supporting references
                                </span>
                              )}

                              {/* Element / Target Section Mapping */}
                              {item.elements.length > 0 && (
                                <span className="text-[11px] font-medium text-amber-300/90 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded">
                                  Supports: {item.elements.join(', ')}
                                </span>
                              )}

                              {/* Source Reference if present */}
                              {item.sourceRefs.length > 0 && (
                                <span className="text-[11px] font-mono text-slate-400 bg-slate-800/60 px-1.5 py-0.5 rounded truncate max-w-xs" title={item.sourceRefs.join(', ')}>
                                  Ref: {item.sourceRefs.join(', ')}
                                </span>
                              )}
                            </div>

                            {/* Actions: Copy & Inspect */}
                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => handleCopy(item.id, item.displayExcerpt)}
                                className="text-[12px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
                                title="Copy excerpt to clipboard"
                              >
                                {copiedId === item.id ? 'Copied ✓' : 'Copy'}
                              </button>
                              <button
                                onClick={() => toggleProvenance(item.id)}
                                className={`text-[12px] px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                                  isProvOpen
                                    ? 'bg-blue-600/20 border-blue-500/40 text-blue-300'
                                    : 'bg-slate-800/60 border-slate-700 text-slate-400 hover:text-slate-200'
                                }`}
                                aria-expanded={isProvOpen}
                              >
                                {isProvOpen ? 'Hide Trace' : 'Inspect Trace'}
                              </button>
                            </div>
                          </div>

                          {/* Readable Excerpt Content */}
                          <div className="text-slate-200 leading-relaxed">
                            {isLong && !isOpen ? (
                              <p className="line-clamp-3 text-slate-300">
                                {item.displayExcerpt.slice(0, 240)}…
                              </p>
                            ) : (
                              <div className="whitespace-pre-line text-slate-300">
                                {item.displayExcerpt}
                              </div>
                            )}

                            {isLong && (
                              <button
                                onClick={() => toggleExcerptExpand(item.id)}
                                className="text-[12px] text-blue-400 hover:underline mt-1 cursor-pointer inline-block"
                              >
                                {isOpen ? 'Show less' : 'Show full excerpt'}
                              </button>
                            )}
                          </div>

                          {/* Technical Provenance Drawer */}
                          {isProvOpen && (
                            <div className="pt-2.5 mt-2 border-t border-slate-800/80 bg-slate-950/60 -mx-3 -mb-3 p-3 rounded-b-md space-y-2">
                              <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold">
                                <span>Underlying Citations &amp; Ingestion Metadata</span>
                                <span>{item.citations.length} raw {item.citations.length === 1 ? 'record' : 'records'}</span>
                              </div>

                              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                                {item.citations.map((c, idx) => (
                                  <div
                                    key={c.citation_id || idx}
                                    className="p-2 rounded bg-slate-900 border border-slate-800/80 text-[12px] font-mono text-slate-400 space-y-0.5"
                                  >
                                    <div className="flex items-center justify-between flex-wrap gap-1">
                                      <span className="text-blue-400 font-sans font-medium">
                                        Citation #{idx + 1}
                                      </span>
                                      <span className="text-[11px] text-slate-500">
                                        ID: {c.citation_id}
                                      </span>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-2 gap-y-0.5 text-[11px] pt-1 border-t border-slate-800/60">
                                      <div>
                                        <span className="text-slate-500">Fragment ID: </span>
                                        <span className="text-slate-300">{c.fragment_id}</span>
                                      </div>
                                      <div>
                                        <span className="text-slate-500">Source Type: </span>
                                        <span className="text-slate-300">{c.source_type ?? 'unattributed'}</span>
                                      </div>
                                      {c.source_ref && (
                                        <div className="col-span-1 sm:col-span-2">
                                          <span className="text-slate-500">Source Ref: </span>
                                          <span className="text-slate-300">{c.source_ref}</span>
                                        </div>
                                      )}
                                      {c.element && (
                                        <div className="col-span-1 sm:col-span-2">
                                          <span className="text-slate-500">Element: </span>
                                          <span className="text-slate-300">{c.element}</span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Trust and Governance Safeguard Footer */}
          <div className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80 text-[12px] text-slate-400 flex items-start gap-2">
            <span className="text-blue-400 text-xs shrink-0 font-semibold">ℹ</span>
            <p>
              <strong className="text-slate-300 font-medium">Source Traceability: </strong>
              Citations identify stored meeting transcripts and reference documents used during AI procedure synthesis. Citations verify archival provenance and evidentiary basis, not statutory college council ratification.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
