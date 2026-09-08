import { ArrowUpRight, BookOpen, ChevronDown, CircleHelp, FileCheck2, FolderOpen, GitBranch, LayoutDashboard, ShieldCheck, Sparkles, TrendingUp, X } from 'lucide-react'
import type { StudioSummary } from '@/types'
export type TabType = 'overview' | 'provenance' | 'countersign' | 'analytics' | 'certificates' | 'examples' | 'help'
export const tabLabels: Record<TabType, string> = { overview: 'Overview', provenance: 'Asset library', countersign: 'Approvals', analytics: 'Insights', certificates: 'Certificates', examples: 'Example gallery', help: 'Help & getting started' }
interface Props { activeTab: TabType; onSelectTab: (tab: TabType) => void; summary: StudioSummary | null; isMobileOpen: boolean; onCloseMobile: () => void }
export function Sidebar({ activeTab, onSelectTab, summary, isMobileOpen, onCloseMobile }: Props) {
  const navigate = (tab: TabType) => { onSelectTab(tab); onCloseMobile() }
  const item = (id: TabType, Icon: typeof LayoutDashboard) => <button key={id} className={`nav-item ${activeTab === id ? 'active' : ''}`} onClick={() => navigate(id)} aria-current={activeTab === id ? 'page' : undefined}><Icon size={18} /><span>{tabLabels[id]}</span>{id === 'countersign' && !!summary?.pending_approvals && <span className="nav-count">{summary.pending_approvals}</span>}{id === 'examples' && <span className="new-tag">Try it</span>}</button>
  return <>
    {isMobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onCloseMobile} />}
    <aside className={`sidebar ${isMobileOpen ? 'sidebar-open' : ''}`} aria-label="Main navigation" onKeyDown={e => { if (e.key === 'Escape') onCloseMobile() }}>
      <a className="brand" href="#overview" onClick={onCloseMobile}><span className="brand-mark"><ShieldCheck size={25} strokeWidth={1.8} /></span><span>doctus<span className="brand-dot">.</span></span><span className="brand-ai">AI</span></a>
      <button className="mobile-close icon-button" aria-label="Close navigation" onClick={onCloseMobile}><X size={20} /></button>
      <div className="workspace-selector"><div className="workspace-avatar">E</div><div><strong>Echo Studio</strong><span>Sample workspace</span></div><ChevronDown size={15} aria-hidden="true" /></div>
      <span className="nav-label">WORKSPACE</span>
      <nav>{item('overview', LayoutDashboard)}{item('provenance', FolderOpen)}{item('countersign', FileCheck2)}{item('analytics', TrendingUp)}{item('certificates', ShieldCheck)}</nav>
      <span className="nav-label resource-label">RESOURCES</span>
      <nav>{item('examples', Sparkles)}{item('help', CircleHelp)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-tip"><span className="tip-icon"><GitBranch size={19} /></span><h3>Create with confidence.</h3><p>Understand the rights behind every asset, before you publish.</p><button onClick={() => navigate('help')}>Explore the guide <ArrowUpRight size={15} /></button></div><div className="workspace-person"><span className="person-avatar">ES</span><div><strong>Echo Studio</strong><span>Sample workspace · No sign-in</span></div><BookOpen size={16} /></div></div>
    </aside>
  </>
}
