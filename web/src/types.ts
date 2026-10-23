export type Phase =
  | "await_roll"
  | "await_jail"
  | "await_buy"
  | "await_auction"
  | "await_trade"
  | "await_debt"
  | "await_manage"
  | "game_over";

export interface Square {
  idx: number;
  short: string;
  name: string;
  type: string;
  group: string | null;
  price: number | null;
  rents: number[] | null;
  house_cost: number | null;
  mortgage: number | null;
  amount?: number;
}

export interface Player {
  pid: number;
  name: string;
  glyph: string;
  color: string;
  cash: number;
  pos: number;
  in_jail: boolean;
  jail_rolls: number;
  goojf: number;
  bankrupt: boolean;
}

export interface DecisionOption {
  action: string;
  label: string;
  payload: Record<string, unknown>;
}

export interface TradeTerms {
  cash: number;
  properties: number[];
  goojf: number;
}

export interface PendingDecision {
  type: string;
  player: number;
  prompt: string;
  options: DecisionOption[];
  idx?: number;
  price?: number;
  then?: string | null;
  amount?: number;
  creditor?: number | null;
  creditors?: Array<{ player: number; amount: number }>;
  reason?: string;
  unit?: number;
  participants?: number[];
  passed?: number[];
  active?: number[];
  high_bid?: number | null;
  high_bidder?: number | null;
  min_bid?: number;
  max_bid?: number;
  bank?: boolean;
  proposer?: number;
  recipient?: number;
  give?: TradeTerms;
  want?: TradeTerms;
  resume_phase?: Phase;
}

export interface GameState {
  squares: Square[];
  players: Player[];
  owner: Array<number | null>;
  houses: number[];
  mortgaged: boolean[];
  current: number;
  turn: number;
  doubles: number;
  dice: [number, number] | null;
  phase: Phase;
  pending: PendingDecision | null;
  winner: number | null;
  log: string[];
  bank_houses?: number;
  bank_hotels?: number;
  run_id?: string;
  agent_seats?: number[];
  mode?: "manual" | "mixed";
  policy?: string | null;
  promoted?: boolean;
}

export interface GameSetup {
  n_players: number;
  agent_seats: number[];
}

export interface Anim {
  mover: number;
  path: number[];
}

export interface ActionResult {
  ok: boolean;
  error?: string;
  state: GameState;
  events?: string[];
  anim?: Anim | null;
  run_id?: string;
  action?: string;
}

export interface RunSummary {
  id: string;
  kind: "manual" | "agent" | "mixed";
  label: string;
  seed: number | null;
  n_players: number;
  policy: string | null;
  agent_seats?: number[];
  promoted: boolean;
  created_at: string;
  status: "running" | "done" | "stopped" | "error";
  winner: number | null;
  steps: number;
  turns: number;
  phase: Phase;
  cash: number[];
  error: string | null;
}

export interface TraceStep {
  seq: number;
  action: string;
  payload: Record<string, unknown>;
  actor: number;
  phase_before: Phase;
  pending_before: PendingDecision | null;
  state: GameState;
  events: string[];
  anim: Anim | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface RunTrace extends Omit<RunSummary, "steps"> {
  initial: GameState;
  steps: TraceStep[];
}

export interface AnalysisOverview {
  labels: string[];
  matrix: number[][];
  stationary: number[];
  hittingTimes: Record<string, number[]>;
  note: string;
}

export interface GameAnalysisPlayer {
  pid: number;
  name: string;
  glyph: string;
  color: string;
  bankrupt: boolean;
  final_cash: number;
  final_net_worth: number;
  properties: number;
  monopolies: number;
  houses: number;
  hotels: number;
  mortgaged: number;
  peak_cash: number;
  peak_net_worth: number;
}

export interface GameAnalysisTimeline {
  labels: string[];
  turns: number[];
  cash: number[][];
  net_worth: number[][];
  properties: number[][];
}

export interface ObservedTransitions {
  labels: string[];
  counts: number[][];
  total: number;
}

export interface GameAnalysis {
  run: RunSummary;
  winner: number | null;
  steps: number;
  turns: number;
  bankrupt_count: number;
  players: GameAnalysisPlayer[];
  timeline: GameAnalysisTimeline;
  actions: Record<string, number>;
  rolls: Record<string, number>;
  observed_transitions: ObservedTransitions;
}
