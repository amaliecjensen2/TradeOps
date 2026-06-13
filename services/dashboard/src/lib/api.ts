/**
 * Typet API klient. Alle komponenter importerer herfra, aldrig fetch() direkte.
 * Base URL sættes via NEXT_PUBLIC_API_URL env var injiceret af Helm/Next.js.
 */

const BASE = "/api/trader";

export interface SystemStatus {
    adapter_connected: boolean;
    halted: boolean;
    halt_reason: string;
    account: string;
}

export interface Position {
    symbol: string;
    position: number;
    avg_cost: number;
    market_value: number | null;
    market_price: number | null;
}

export interface PnLSnapshot {
    daily_pnl: number;
    unrealized_pnl: number;
    realized_pnl: number;
    net_liquidation: number | null;
}

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { next: { revalidate: 0 } });
    if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
    return res.json() as Promise<T>;
}

export const api = {
    status: () => get<SystemStatus>("/status"),
    positions: () => get<Position[]>("/positions"),
    pnl: () => get<PnLSnapshot>("/pnl"),
};
