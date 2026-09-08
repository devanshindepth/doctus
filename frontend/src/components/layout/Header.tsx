import React, { useState } from 'react'
import {
  Activity,
  CheckCircle2,
  Database,
  FastForward,
  Menu,
  Play,
  RotateCcw,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { StudioSummary } from '@/types'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

interface HeaderProps {
  summary: StudioSummary | null
  onRefresh: () => void
  onToggleMobileSidebar: () => void
}

const BEAT_NAMES = [
  'Ready to begin',
  'Beat 1: Veo Generation (Signed C2PA)',
  'Beat 2: Likeness Consent Check (Allowed)',
  'Beat 3: Composite Multi-Track Clip',
  'Beat 4: Festival Publish (Allowed)',
  'Beat 5: Trailer Release Attempt (Blocked)',
  'Beat 6: Autonomous ODRL Negotiation',
  'Beat 7: Human Countersignature',
  'Beat 8: Re-publish Trailer (Allowed!)',
]

export const Header: React.FC<HeaderProps> = ({ summary, onRefresh, onToggleMobileSidebar }) => {
  const [isStepping, setIsStepping] = useState(false)
  const [isAutoPlaying, setIsAutoPlaying] = useState(false)
  const [isResetting, setIsResetting] = useState(false)

  const currentBeat = summary?.current_beat || 0
  const isCompleted = currentBeat >= 8

  const handleStep = async (targetBeat: number | null = null) => {
    try {
      setIsStepping(true)
      const res = await api.runDemoBeat(targetBeat)
      if (res.ok) {
        toast.success(`Beat ${res.beat} completed successfully!`, {
          description: BEAT_NAMES[res.beat] || 'Next step executed',
        })
        onRefresh()
      } else {
        toast.error(res.message || 'Error running beat')
      }
    } catch (err: any) {
      toast.error(`Step failed: ${err.message}`)
    } finally {
      setIsStepping(false)
    }
  }

  const handleAutoPlay = async () => {
    if (isAutoPlaying) return
    setIsAutoPlaying(true)
    toast.info('Starting 8-Beat Demo Arc Auto-Play...')

    try {
      const startBeat = currentBeat >= 8 ? 1 : currentBeat + 1
      for (let b = startBeat; b <= 8; b++) {
        const res = await api.runDemoBeat(b)
        if (!res.ok) {
          toast.error(`Auto-play halted at beat ${b}: ${res.message}`)
          break
        }
        toast.success(`Beat ${b} Executed`, {
          description: BEAT_NAMES[b],
          duration: 2500,
        })
        onRefresh()
        await new Promise((r) => setTimeout(r, 1400))
      }
      toast.success('🎉 Full 8-Beat Demo Arc Successfully Verified!')
    } catch (err: any) {
      toast.error(`Auto-play error: ${err.message}`)
    } finally {
      setIsAutoPlaying(false)
      onRefresh()
    }
  }

  const handleReset = async () => {
    try {
      setIsResetting(true)
      await api.resetDemo()
      toast.success('Studio state reset to clean baseline.')
      onRefresh()
    } catch (err: any) {
      toast.error(`Reset failed: ${err.message}`)
    } finally {
      setIsResetting(false)
    }
  }

  return (
    <header className="h-16 glass-panel border-b border-dark-800 flex items-center justify-between px-4 sm:px-6 z-20 shrink-0 sticky top-0">
      <div className="flex items-center gap-3 md:gap-4">
        <button
          onClick={onToggleMobileSidebar}
          className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-dark-800 transition"
          aria-label="Open mobile navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2">
          <h1 className="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
            Clearance Studio
          </h1>
          <span className="hidden sm:inline-block text-xs text-dark-500 font-mono">v2.0</span>
        </div>

        {/* Live system indicators */}
        <div className="hidden lg:flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-dark-900/90 rounded-md border border-dark-750">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-slate-400">Gate:</span>
            <span className="text-emerald-400 font-semibold">Active</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-dark-900/90 rounded-md border border-dark-750">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-slate-400">P50:</span>
            <span className="text-amber-400 font-mono font-medium">
              {summary ? `${summary.p50_latency_ms.toFixed(2)} ms` : '--'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-dark-900/90 rounded-md border border-dark-750">
            <Database className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">Engine:</span>
            <span className="text-sky-400 font-medium">
              {summary?.is_mock_clickhouse ? 'Local Mirror' : 'ClickHouse Cloud'}
            </span>
          </div>
        </div>
      </div>

      {/* Demo Arc Controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        <div className="hidden md:flex flex-col items-end text-right">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">
            Demo Arc
          </span>
          <span
            className={`text-xs font-medium font-mono ${
              isCompleted ? 'text-emerald-400' : 'text-crimson-400'
            }`}
          >
            {isCompleted ? 'Arc Complete (8/8)' : `Beat ${currentBeat} → Next: Beat ${currentBeat + 1}`}
          </span>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => handleStep()}
          disabled={isStepping || isAutoPlaying}
          title="Step Next Beat"
          className="hidden sm:inline-flex"
        >
          <FastForward className="w-3.5 h-3.5 text-crimson-400" />
          <span className="hidden lg:inline">Step Beat</span>
        </Button>

        <Button
          variant="primary"
          size="sm"
          onClick={handleAutoPlay}
          isLoading={isAutoPlaying}
          disabled={isStepping}
          className="shadow-glow-crimson"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          <span>{isAutoPlaying ? 'Running...' : 'Auto-Play Arc'}</span>
        </Button>

        <button
          onClick={handleReset}
          disabled={isResetting || isAutoPlaying}
          className="p-2 rounded-lg bg-dark-850 hover:bg-dark-800 border border-dark-750 text-slate-400 hover:text-slate-200 transition"
          title="Reset Studio Demo State"
          aria-label="Reset Demo State"
        >
          <RotateCcw className={`w-4 h-4 ${isResetting ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </header>
  )
}
