import React from 'react'
import {
  Activity,
  Download,
  Film,
  FileVideo,
  GitMerge,
  LayoutDashboard,
  PenTool,
  ShieldCheck,
  X,
} from 'lucide-react'
import { StudioSummary } from '@/types'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'

export type TabType = 'overview' | 'provenance' | 'countersign' | 'analytics'

interface SidebarProps {
  activeTab: TabType
  onSelectTab: (tab: TabType) => void
  summary: StudioSummary | null
  isMobileOpen: boolean
  onCloseMobile: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  summary,
  isMobileOpen,
  onCloseMobile,
}) => {
  const pendingApprovals = summary?.pending_approvals || 0

  const handleExportCert = () => {
    window.open(api.getCertificateDownloadUrl(), '_blank')
  }

  const navItems = [
    {
      id: 'overview' as TabType,
      label: 'Clearance Overview',
      icon: LayoutDashboard,
    },
    {
      id: 'provenance' as TabType,
      label: 'Asset Lineage (DAG)',
      icon: GitMerge,
    },
    {
      id: 'countersign' as TabType,
      label: 'Legal Queue',
      icon: PenTool,
      badge: pendingApprovals > 0 ? pendingApprovals : null,
    },
    {
      id: 'analytics' as TabType,
      label: 'Engine Telemetry',
      icon: Activity,
    },
  ]

  const sidebarContent = (
    <div className="flex flex-col h-full justify-between select-none">
      <div>
        {/* Studio Branding */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-dark-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-crimson-600 flex items-center justify-center shadow-glow-crimson">
              <Film className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-bold text-sm tracking-wide text-white block">DOCTUS</span>
              <span className="text-[10px] text-slate-500 font-mono tracking-wider">AI RIGHTS CLEARANCE</span>
            </div>
          </div>

          <button
            onClick={onCloseMobile}
            className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-dark-800"
            aria-label="Close navigation drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Project Selector Box */}
        <div className="p-4">
          <p className="text-[10px] uppercase font-semibold text-slate-500 mb-2 px-2 tracking-wider">
            Active Production
          </p>
          <div className="px-3 py-2 bg-dark-850 rounded-lg border border-dark-750 flex items-center gap-2.5">
            <FileVideo className="w-4 h-4 text-crimson-500 shrink-0" />
            <div className="min-w-0 flex-1">
              <span className="text-xs font-semibold text-slate-200 block truncate">The Last Echo</span>
              <span className="text-[10px] text-slate-500 block truncate">Veo + Custom Audio Bed</span>
            </div>
          </div>

          {/* Navigation Links */}
          <p className="text-[10px] uppercase font-semibold text-slate-500 mt-6 mb-2 px-2 tracking-wider">
            Clearance Studio
          </p>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = activeTab === item.id

              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onSelectTab(item.id)
                    onCloseMobile()
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs md:text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-crimson-600/15 text-crimson-400 border border-crimson-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-dark-850'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-crimson-500' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>

                  {item.badge !== null && item.badge !== undefined && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
                      {item.badge}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* User info & E&O Certificate Export */}
      <div className="p-4 border-t border-dark-800/80 bg-dark-900/40">
        <div className="flex items-center gap-3 mb-4 px-2">
          <div className="w-8 h-8 rounded-full bg-crimson-900/60 border border-crimson-600/40 flex items-center justify-center text-xs font-bold text-crimson-300">
            EV
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-slate-200 truncate">Elena Vance</p>
            <p className="text-[10px] text-slate-500 truncate">Studio Legal Lead</p>
          </div>
        </div>

        <button
          onClick={handleExportCert}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-750 border border-dark-700 hover:border-emerald-500/40 rounded-lg text-xs font-medium text-slate-200 transition group"
        >
          <ShieldCheck className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
          <span>Export E&amp;O Cert</span>
          <Download className="w-3 h-3 text-slate-500 ml-auto" />
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop fixed sidebar */}
      <aside className="hidden md:flex w-64 bg-dark-900 border-r border-dark-800 flex-col shrink-0 z-30 shadow-2xl">
        {sidebarContent}
      </aside>

      {/* Mobile drawer backdrop and slide-over */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm md:hidden animate-fade-in"
          onClick={onCloseMobile}
        >
          <div
            className="fixed inset-y-0 left-0 w-72 bg-dark-900 border-r border-dark-800 shadow-2xl p-0 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  )
}
