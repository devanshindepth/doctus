import React, { useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  CheckCircle2,
  FileBadge,
  GitBranch,
  GitMerge,
  Info,
  Layers,
  LayoutGrid,
  Network,
  Shield,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react'
import { ProvenanceGraphData, ProvenanceNode } from '@/types'
import { Card, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'

interface LineagePageProps {
  graph: ProvenanceGraphData | null
  onInspectAsset?: (assetId: string) => void
}

export const LineagePage: React.FC<LineagePageProps> = ({ graph }) => {
  const [viewMode, setViewMode] = useState<'dag' | 'grid'>('dag')
  const [selectedNode, setSelectedNode] = useState<ProvenanceNode | null>(null)

  const nodesList = graph?.nodes || []
  const linksList = graph?.links || []

  // Transform graph data into React Flow nodes and edges with auto-layout
  const { flowNodes, flowEdges } = useMemo(() => {
    if (!nodesList.length) return { flowNodes: [], flowEdges: [] }

    // Group nodes into topological layers (roots vs composites)
    const ingredientIds = new Set(linksList.map((l) => l.source))
    const compositeIds = new Set(linksList.map((l) => l.target))

    const roots = nodesList.filter((n) => !compositeIds.has(n.id))
    const composites = nodesList.filter((n) => compositeIds.has(n.id))

    const flowNodes: Node[] = []
    const spacingX = 260
    const spacingY = 140

    // Place roots on layer 0
    roots.forEach((node, idx) => {
      flowNodes.push({
        id: node.id,
        data: {
          label: (
            <div className="p-3 text-left">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-[11px] font-mono font-bold text-crimson-400 truncate max-w-[130px]">
                  {node.id}
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-dark-800 text-slate-400 font-mono">
                  ROOT
                </span>
              </div>
              <p className="text-xs font-semibold text-slate-100 truncate">{node.label}</p>
              <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
                <span>{node.claims_count} C2PA Claims</span>
                <span
                  className={
                    node.has_untrusted ? 'text-crimson-400 font-bold' : 'text-emerald-400 font-bold'
                  }
                >
                  {node.has_untrusted ? 'Untrusted' : 'Verified'}
                </span>
              </div>
            </div>
          ),
          rawNode: node,
        },
        position: { x: 50 + (idx % 3) * spacingX, y: 50 + Math.floor(idx / 3) * spacingY },
        style: {
          background: '#0e1117',
          color: '#f8fafc',
          border: node.has_untrusted ? '1px solid #ef4444' : '1px solid #22c55e',
          borderRadius: '12px',
          width: 220,
          boxShadow: node.has_untrusted
            ? '0 0 15px -3px rgba(239, 68, 68, 0.25)'
            : '0 0 15px -3px rgba(34, 197, 94, 0.25)',
        },
      })
    })

    // Place composites on layer 1 & 2
    composites.forEach((node, idx) => {
      flowNodes.push({
        id: node.id,
        data: {
          label: (
            <div className="p-3 text-left">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-[11px] font-mono font-bold text-sky-400 truncate max-w-[130px]">
                  {node.id}
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-sky-950/60 text-sky-300 font-mono border border-sky-800">
                  COMPOSITE
                </span>
              </div>
              <p className="text-xs font-semibold text-slate-100 truncate">{node.label}</p>
              <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
                <span>{node.claims_count} C2PA Claims</span>
                <span
                  className={
                    node.has_untrusted ? 'text-crimson-400 font-bold' : 'text-emerald-400 font-bold'
                  }
                >
                  {node.has_untrusted ? 'Untrusted' : 'Verified'}
                </span>
              </div>
            </div>
          ),
          rawNode: node,
        },
        position: { x: 180 + (idx % 2) * (spacingX * 1.2), y: 280 + Math.floor(idx / 2) * spacingY },
        style: {
          background: '#0e1117',
          color: '#f8fafc',
          border: node.has_untrusted ? '1px solid #ef4444' : '1px solid #38bdf8',
          borderRadius: '12px',
          width: 220,
          boxShadow: '0 0 15px -3px rgba(56, 189, 248, 0.25)',
        },
      })
    })

    const flowEdges: Edge[] = linksList.map((l, i) => ({
      id: `edge-${i}-${l.source}-${l.target}`,
      source: l.source,
      target: l.target,
      animated: true,
      style: { stroke: '#dc2626', strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#dc2626',
      },
    }))

    return { flowNodes, flowEdges }
  }, [nodesList, linksList])

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-fade-in">
      {/* Header with Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <GitMerge className="w-5 h-5 text-crimson-500" />
            <span>Asset Lineage &amp; C2PA Provenance DAG</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Verifiable cryptographic chain-of-title and ODRL assertions across all sub-components.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-dark-900 p-1 rounded-xl border border-dark-750 self-start">
          <button
            onClick={() => setViewMode('dag')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === 'dag'
                ? 'bg-crimson-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Interactive DAG</span>
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === 'grid'
                ? 'bg-crimson-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" />
            <span>Card Grid</span>
          </button>
        </div>
      </div>

      {/* Main View Area */}
      {viewMode === 'dag' ? (
        <div className="relative glass-panel rounded-2xl border border-dark-750/80 overflow-hidden h-[600px] shadow-2xl">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            onNodeClick={(_, node) => {
              const raw = (node.data as any)?.rawNode
              if (raw) setSelectedNode(raw)
            }}
            fitView
          >
            <Background color="#1e232d" gap={16} />
            <Controls className="bg-dark-900 border border-dark-700 text-white" />
            <MiniMap
              nodeColor={(n) => {
                return (n.data as any)?.rawNode?.has_untrusted ? '#ef4444' : '#22c55e'
              }}
              className="bg-dark-950 border border-dark-800 rounded-lg overflow-hidden"
            />
          </ReactFlow>

          <div className="absolute top-4 right-4 z-10 px-3 py-1.5 bg-dark-950/80 backdrop-blur-md rounded-lg border border-dark-700 text-[11px] text-slate-300 flex items-center gap-3">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Verified Closure</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-crimson-500" />
              <span>Untrusted / Blocked</span>
            </span>
          </div>
        </div>
      ) : (
        /* Card Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {nodesList.map((node) => (
            <Card
              key={node.id}
              className="hover:border-crimson-500/50 cursor-pointer flex flex-col justify-between"
              onClick={() => setSelectedNode(node)}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-mono font-bold text-crimson-400">{node.id}</span>
                  <Badge variant={node.is_composite ? 'info' : 'neutral'}>
                    {node.is_composite ? 'Composite' : 'Root Asset'}
                  </Badge>
                </div>

                <h4 className="text-sm font-bold text-white mb-3">{node.label}</h4>

                <div className="space-y-2 mb-4">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold tracking-wider block">
                    C2PA Assertions ({node.claims.length}):
                  </span>
                  {node.claims.length === 0 ? (
                    <p className="text-xs text-slate-500">No C2PA claims attached</p>
                  ) : (
                    node.claims.map((c) => (
                      <div
                        key={c.claim_id}
                        className="p-2 rounded-lg bg-dark-900 border border-dark-750 text-xs font-mono flex items-center justify-between"
                      >
                        <span className="text-slate-300 font-semibold">{c.kind}</span>
                        <Badge variant={c.trusted ? 'success' : 'danger'}>
                          {c.trusted ? 'VERIFIED' : 'UNTRUSTED'}
                        </Badge>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="pt-3 border-t border-dark-750 flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Authority: {node.has_untrusted ? 'Untrusted Signer' : 'Doctus Root'}</span>
                </span>
                <span className="text-crimson-400 font-semibold hover:underline">Inspect</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Asset Inspector Drawer */}
      {selectedNode && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-dark-900 border-l border-dark-750 shadow-2xl p-6 flex flex-col justify-between glass-panel animate-fade-in">
          <div>
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-dark-750">
              <div className="flex items-center gap-2">
                <FileBadge className="w-5 h-5 text-crimson-500" />
                <h3 className="text-base font-bold text-white">Asset Inspector</h3>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-dark-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold block">
                  Asset Identifier
                </span>
                <p className="text-sm font-mono font-bold text-crimson-400">{selectedNode.id}</p>
              </div>

              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold block">
                  Label
                </span>
                <p className="text-sm font-semibold text-slate-200">{selectedNode.label}</p>
              </div>

              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold block">
                  Asset Type
                </span>
                <Badge variant={selectedNode.is_composite ? 'info' : 'neutral'} className="mt-1">
                  {selectedNode.is_composite ? 'Composite (Multi-ingredient)' : 'Root Media Asset'}
                </Badge>
              </div>

              <div className="pt-3 border-t border-dark-750">
                <span className="text-slate-400 uppercase tracking-wider text-xs font-bold block mb-2">
                  C2PA Assertions ({selectedNode.claims.length})
                </span>
                <div className="space-y-2">
                  {selectedNode.claims.map((c) => (
                    <div
                      key={c.claim_id}
                      className="p-3 bg-dark-950 rounded-xl border border-dark-750 space-y-1 font-mono text-[11px]"
                    >
                      <div className="flex items-center justify-between">
                        <strong className="text-slate-200">{c.kind}</strong>
                        <Badge variant={c.trusted ? 'success' : 'danger'}>
                          {c.trusted ? 'VERIFIED' : 'UNTRUSTED'}
                        </Badge>
                      </div>
                      <p className="text-slate-400 text-[10px]">Claim ID: {c.claim_id}</p>
                      <p className="text-slate-500 text-[10px]">Signer: {c.signer}</p>
                      {c.valid_until && (
                        <p className="text-amber-400 text-[10px]">Expires: {c.valid_until}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <Button
            variant="outline"
            className="w-full mt-6"
            onClick={() => setSelectedNode(null)}
          >
            Close Inspector
          </Button>
        </div>
      )}
    </div>
  )
}
