import { useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, MarkerType, type Node, type Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ArrowRight, FileCheck2, Film, FolderOpen, GitBranch, LayoutGrid, Music2, Search, ShieldCheck } from 'lucide-react'
import type { ProvenanceGraphData, ProvenanceNode } from '@/types'
import { assetName } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
interface Props { graph: ProvenanceGraphData | null }
const media: Record<string, string> = { ast_hero_shot_v1: '/media/ast_hero_shot_v1.jpg', ast_composite_v1: '/media/ast_composite_v1.jpg', ast_talent_frame_v1: '/media/ast_talent_frame_v1.jpg', ast_music_bed_v1: '/media/ast_music_bed_v1.jpg' }
export function LineagePage({ graph }: Props) {
  const [view, setView] = useState<'grid' | 'graph'>('grid')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<ProvenanceNode | null>(null)
  const assets = graph?.nodes || []
  const filtered = assets.filter(n => `${assetName(n.id)} ${n.id} ${n.label}`.toLowerCase().includes(search.toLowerCase()))
  const { nodes, edges } = useMemo(() => {
    const links = graph?.links || []
    // Calculate a layer from ancestry, keeping deeper composites below their ingredients.
    const depth = (id: string, seen = new Set<string>()): number => {
      if (seen.has(id)) return 0
      const next = new Set(seen).add(id)
      return Math.max(0, ...links.filter(l => l.target === id).map(l => depth(l.source, next) + 1))
    }
    const layers: Record<number, number> = {}
    const nodes: Node[] = (graph?.nodes || []).map(n => {
      const layer = depth(n.id); const column = layers[layer] || 0; layers[layer] = column + 1
      return { id: n.id, position: { x: column * 265, y: layer * 190 }, data: { label: <div className="flow-label"><span><Film size={16} />{n.is_composite ? 'Combined asset' : 'Source asset'}</span><strong>{assetName(n.id)}</strong><small>{n.claims_count} rights records · {n.has_untrusted ? 'Review needed' : n.claims_count ? 'Trusted signatures' : 'No records'}</small></div> }, style: { width: 230, background: '#fff', color: '#213d38', border: `1px solid ${n.has_untrusted ? '#d8ab66' : '#b3cfc4'}`, borderRadius: 12, padding: 4 } }
    })
    const edges: Edge[] = links.map((l, i) => ({ id: `edge-${i}`, source: l.source, target: l.target, style: { stroke: '#729b8e', strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#729b8e' } }))
    return { nodes, edges }
  }, [graph])
  return <div className="page-stack"><div className="page-heading"><div><span className="eyebrow">KNOW WHAT’S BEHIND YOUR WORK</span><h1>Your creative library.</h1><p>Explore your assets and the rights records that travel with them.</p></div><Badge variant="neutral" size="md">{assets.length} assets · Sample workspace</Badge></div><div className="library-toolbar"><label className="search-box"><Search size={17} /><input aria-label="Search asset library" placeholder="Search by asset name…" value={search} onChange={e => { setSearch(e.target.value); setView('grid') }} /></label><div className="segmented"><button onClick={() => setView('grid')} className={view === 'grid' ? 'selected' : ''} aria-pressed={view === 'grid'}><LayoutGrid size={15} />Asset cards</button><button onClick={() => { setSearch(''); setView('graph') }} className={view === 'graph' ? 'selected' : ''} aria-pressed={view === 'graph'}><GitBranch size={15} />Rights connections</button></div></div>
    {view === 'grid' ? <div className="asset-grid">{filtered.map(n => <button className="card asset-card" key={n.id} onClick={() => setSelected(n)}><div className={`asset-cover ${n.id.includes('music') ? 'audio-cover' : ''}`}>{media[n.id] ? <img src={media[n.id]} alt={assetName(n.id)} loading="lazy" /> : <Film size={44} />}<span className="asset-cover-type">{n.id.includes('music') ? <Music2 size={14} /> : <Film size={14} />}{n.is_composite ? 'Combined media' : n.id.includes('music') ? 'Audio rights' : 'Visual asset'}</span></div><div className="asset-card-body"><h2>{assetName(n.id)}</h2><p>{n.label || 'Registered media asset'}</p><div className="asset-card-meta"><span><FileCheck2 size={14} />{n.claims_count} records</span><Badge variant={n.has_untrusted || !n.claims_count ? 'warning' : 'success'}>{n.has_untrusted ? 'Review needed' : n.claims_count ? 'Trusted signatures' : 'No records'}</Badge></div><span className="asset-inspect">View rights details <ArrowRight size={15} /></span></div></button>)}</div> : <div className="card graph-canvas"><ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} onNodeClick={(_, n) => setSelected(assets.find(a => a.id === n.id) || null)}><Background gap={24} color="#d4dfda" /><Controls /></ReactFlow></div>}
    {view === 'grid' && !filtered.length && <div className="card empty-state"><FolderOpen size={32} /><h2>No assets found</h2><p>Try a different name or clear your search.</p></div>}
    <div className="notice"><ShieldCheck size={20} /><p>A trusted signature tells you who signed a rights record. Always run a clearance check for your specific channel and region before publishing.</p></div>
    <Modal isOpen={!!selected} onClose={() => setSelected(null)} title={selected ? assetName(selected.id) : 'Asset details'}>{selected && <div className="page-stack"><p className="muted">{selected.label}</p><div className="detail-summary"><span className="eyebrow">ASSET REFERENCE</span><code>{selected.id}</code></div><h3>Attached rights records</h3>{selected.claims.length ? selected.claims.map(c => <div className="claim-row" key={c.claim_id}><div className="claim-top"><strong className="capitalize">{c.kind.toLowerCase().replaceAll('_',' ')}</strong><Badge variant={c.trusted ? 'success' : 'warning'}>{c.trusted ? 'Trusted signature' : 'Needs verification'}</Badge></div><p>Signed by {c.signer}</p><small>Expires: {c.valid_until ? new Date(c.valid_until).toLocaleDateString() : 'No expiry recorded'}</small><details><summary>Record reference</summary><code>{c.claim_id}</code></details></div>) : <p>No rights records are attached. Clearance cannot be assumed.</p>}<h3>Included ingredients</h3>{graph?.links.filter(l => l.target === selected.id).length ? graph.links.filter(l => l.target === selected.id).map(l => <div className="ingredient-row" key={l.source}><Film size={17} /><span>{assetName(l.source)}</span></div>) : <p className="muted">This is a source asset with no recorded ingredients.</p>}</div>}</Modal>
  </div>
}
