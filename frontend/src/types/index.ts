export interface StudioSummary {
  studio_assets: number
  verified_claims: number
  clearance_rate: number
  allows: number
  denies: number
  p50_latency_ms: number
  countersign_actions: number
  pending_approvals: number
  current_beat: number
  graph_version: number
  backend: string
  is_mock_clickhouse: boolean
}

export interface ClaimItem {
  claim_id: string
  kind: string
  signer: string
  trusted: boolean
  valid_until?: string | null
}

export interface ProvenanceNode {
  id: string
  label: string
  is_composite: boolean
  has_untrusted: boolean
  claims_count: number
  claims: ClaimItem[]
}

export interface ProvenanceLink {
  source: string
  target: string
}

export interface ProvenanceGraphData {
  nodes: ProvenanceNode[]
  links: ProvenanceLink[]
}

export interface DecisionRecord {
  decision_id: number
  ts: string
  asset_id: string
  verb: string
  channel?: string | null
  territory?: string | null
  allowed: boolean
  reason: string
  detail?: string | null
  missing_claim_kind?: string | null
  failed_ingredient?: string | null
  negotiation_hint?: string | null
  action_json?: string | null
  claims_evaluated_json?: string | null
  graph_version: number
}

export interface PendingDraft {
  draft_id: string
  asset_id: string
  kind: string
  odrl_json: string
  summary: string
  proposed_at?: string
  action?: string
}

export interface LatencyMetrics {
  p50: number
  p90: number
  p95: number
  p99: number
}

export interface ExpiringAlert {
  claim_id: string
  asset_id: string
  days_remaining: number
  status: string
}

export interface AnalyticsData {
  latencies: LatencyMetrics
  denials: Record<string, number>
  expiring_alerts: ExpiringAlert[]
  chain_depth?: Record<string, any>
}

export interface PreflightVerdict {
  allowed: boolean
  decision_id?: number
  reason: string
  detail?: string
  missing_claim_kind?: string
  failed_ingredient?: string
  negotiation_hint?: string
}

export interface DemoLogEvent {
  beat: number
  status: string
  message: string
  timestamp: string
  data?: any
}
