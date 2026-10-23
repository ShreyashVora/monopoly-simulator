import type { GameState, Square } from "./types";

export const N = 11;

export const FILL: Record<string, string> = {
  brown: "#955436",
  lightblue: "#AAE0FA",
  pink: "#D93A96",
  orange: "#F7941D",
  red: "#ED1B24",
  yellow: "#FEF200",
  green: "#1FB25A",
  darkblue: "#0072BB",
  railroad: "#2B2B2B",
  utility: "#CFCFCF",
};

export const ICONS: Record<string, string> = {
  chest: "\u{1F381}",
  chance: "\u2753",
  tax: "\u{1F4B0}",
};

export const DICE = ["\u2680", "\u2681", "\u2682", "\u2683", "\u2684", "\u2685"];

const QUAD: Array<[number, number]> = [
  [-0.2, -0.2],
  [0.16, -0.2],
  [-0.2, 0.13],
  [0.16, 0.13],
];

const SIX: Array<[number, number]> = [
  [-0.25, -0.18],
  [0, -0.18],
  [0.25, -0.18],
  [-0.25, 0.18],
  [0, 0.18],
  [0.25, 0.18],
];

export function tokenOffset(n: number, i: number): [number, number] {
  const table = n > 4 ? SIX : QUAD;
  return table[i % table.length];
}

export function cellMap(): Record<string, number> {
  const m: Record<string, number> = {};
  for (let c = 1; c <= 11; c++) m[`11,${c}`] = 11 - c;
  for (let r = 1; r <= 11; r++) m[`${r},1`] = 21 - r;
  for (let c = 1; c <= 11; c++) m[`1,${c}`] = 19 + c;
  for (let r = 1; r <= 11; r++) m[`${r},11`] = (29 + r) % 40;
  return m;
}

export const idxAt = cellMap();

export function orientOf(idx: number): "bottom" | "left" | "top" | "right" {
  if (idx >= 0 && idx < 10) return "bottom";
  if (idx >= 10 && idx < 20) return "left";
  if (idx >= 20 && idx < 30) return "top";
  return "right";
}

export function isCorner(s: Square): boolean {
  return ["go", "jail", "free_parking", "go_to_jail"].includes(s.type);
}

export function groupIdxs(state: GameState, idx: number): number[] {
  const g = state.squares[idx].group;
  return state.squares
    .filter((x) => x.group === g && x.type === "street")
    .map((x) => x.idx);
}

export const HOUSE_LIMIT = 32;
export const HOTEL_LIMIT = 12;

export const GROUP_ORDER = [
  "brown",
  "lightblue",
  "pink",
  "orange",
  "red",
  "yellow",
  "green",
  "darkblue",
  "railroad",
  "utility",
];

export const GROUP_LABELS: Record<string, string> = {
  brown: "Brown",
  lightblue: "Light Blue",
  pink: "Pink",
  orange: "Orange",
  red: "Red",
  yellow: "Yellow",
  green: "Green",
  darkblue: "Dark Blue",
  railroad: "Railroads",
  utility: "Utilities",
};

export function groupLabel(group: string | null): string {
  return group ? (GROUP_LABELS[group] ?? group) : "Other";
}

export function bankHouses(state: GameState): number {
  return (
    state.bank_houses ??
    HOUSE_LIMIT - state.houses.reduce((n, h) => n + Math.min(h, 4), 0)
  );
}

export function bankHotels(state: GameState): number {
  return (
    state.bank_hotels ??
    HOTEL_LIMIT - state.houses.filter((h) => h === 5).length
  );
}

export function managingPid(state: GameState): number {
  if (state.phase === "await_debt" && state.pending?.type === "debt")
    return state.pending.player;
  return state.current;
}

export function propertyGroups(
  state: GameState,
  pid: number,
): Array<{ group: string; label: string; idxs: number[] }> {
  const grouped = new Map<string, number[]>();
  state.owner.forEach((owner, idx) => {
    if (owner !== pid) return;
    const group = state.squares[idx].group;
    if (!group || !["street", "railroad", "utility"].includes(state.squares[idx].type))
      return;
    const list = grouped.get(group) ?? [];
    list.push(idx);
    grouped.set(group, list);
  });
  return GROUP_ORDER.filter((group) => grouped.has(group)).map((group) => ({
    group,
    label: groupLabel(group),
    idxs: grouped.get(group) ?? [],
  }));
}

const ASSET_MODES = ["await_roll", "await_manage", "await_jail"];
const SPEND_MODES = ["await_roll", "await_manage", "await_jail"];

export function buildReason(
  state: GameState,
  idx: number,
  pid = state.current,
): string | null {
  const sq = state.squares[idx];
  if (state.winner !== null) return "Game over.";
  if (state.phase === "await_debt") return "Settle the debt first.";
  if (!SPEND_MODES.includes(state.phase)) return "Unavailable right now.";
  if (sq.type !== "street") return "Only streets can be improved.";
  if (state.owner[idx] !== pid) return "Not your property.";
  if (state.houses[idx] >= 5) return "Hotel already built.";
  const g = groupIdxs(state, idx);
  if (!g.every((i) => state.owner[i] === pid))
    return `Own all ${groupLabel(sq.group)} streets to build.`;
  if (g.some((i) => state.mortgaged[i]))
    return `Unmortgage the ${groupLabel(sq.group)} group first.`;
  const h = state.houses[idx];
  if (h !== Math.min(...g.map((i) => state.houses[i])))
    return `Build evenly across ${groupLabel(sq.group)}.`;
  if (h < 4 && bankHouses(state) <= 0) return "No houses left in the bank.";
  if (h === 4 && bankHotels(state) <= 0) return "No hotels left in the bank.";
  const cost = sq.house_cost ?? 0;
  if (state.players[pid].cash < cost) return `Need $${cost}.`;
  return null;
}

export function canBuild(state: GameState, idx: number): boolean {
  return buildReason(state, idx) === null;
}

export function sellReason(
  state: GameState,
  idx: number,
  pid = state.current,
): string | null {
  if (state.winner !== null) return "Game over.";
  if (!ASSET_MODES.includes(state.phase) && state.phase !== "await_debt")
    return "Unavailable right now.";
  if (state.owner[idx] !== pid) return "Not your property.";
  if (state.squares[idx].type !== "street") return "Only streets hold buildings.";
  if (state.houses[idx] < 1) return "No buildings to sell.";
  const g = groupIdxs(state, idx);
  if (state.houses[idx] !== Math.max(...g.map((i) => state.houses[i])))
    return `Sell evenly across ${groupLabel(state.squares[idx].group)}.`;
  if (state.houses[idx] === 5 && bankHouses(state) < 4)
    return "Bank needs four houses to break the hotel.";
  return null;
}

export function canSell(state: GameState, idx: number): boolean {
  return sellReason(state, idx) === null;
}

export function mortgageReason(
  state: GameState,
  idx: number,
  pid = state.current,
): string | null {
  if (state.winner !== null) return "Game over.";
  if (!ASSET_MODES.includes(state.phase) && state.phase !== "await_debt")
    return "Unavailable right now.";
  if (state.owner[idx] !== pid) return "Not your property.";
  if (state.mortgaged[idx]) return "Already mortgaged.";
  if (
    !["street", "railroad", "utility"].includes(state.squares[idx].type)
  )
    return "This cannot be mortgaged.";
  if (groupIdxs(state, idx).some((i) => state.houses[i] > 0))
    return "Sell the group's buildings first.";
  return null;
}

export function canMortgage(state: GameState, idx: number): boolean {
  return mortgageReason(state, idx) === null;
}

export function unmortgageReason(
  state: GameState,
  idx: number,
  pid = state.current,
): string | null {
  if (state.winner !== null) return "Game over.";
  if (state.phase === "await_debt") return "Settle the debt first.";
  if (!SPEND_MODES.includes(state.phase)) return "Unavailable right now.";
  if (state.owner[idx] !== pid) return "Not your property.";
  if (!state.mortgaged[idx]) return "That property is not mortgaged.";
  const cost = unmortgageCost(state, idx);
  if (state.players[pid].cash < cost) return `Need $${cost}.`;
  return null;
}

export function canUnmortgage(state: GameState, idx: number): boolean {
  return unmortgageReason(state, idx) === null;
}

export function unmortgageCost(state: GameState, idx: number): number {
  return Math.ceil((state.squares[idx].mortgage ?? 0) * 1.1);
}

const PHASE_LABELS: Record<string, string> = {
  await_roll: "Roll the dice",
  await_manage: "Manage, then end turn",
  await_buy: "Buy decision",
  await_jail: "Jail decision",
  await_debt: "Raise cash to settle debt",
  game_over: "Game over",
};

export function phaseText(state: GameState): string {
  if (state.winner !== null) return "Game over";
  return PHASE_LABELS[state.phase] ?? "";
}

export function isFreshGame(state: GameState): boolean {
  return (
    state.turn === 1 &&
    state.owner.every((o) => o === null) &&
    state.log.length <= 1
  );
}
