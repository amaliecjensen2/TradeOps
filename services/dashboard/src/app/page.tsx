/**
 * Main dashboard page.
 * Refreshes all panels every 10 seconds via SWR.
 */
"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import StatusBar from "@/components/StatusBar";
import PnLChart from "@/components/PnLChart";
import PositionsTable from "@/components/PositionsTable";
import FillsTable from "@/components/FillsTable";

const REFRESH = 10_000;

export default function Dashboard() {
    const { data: status } = useSWR("status", api.status, { refreshInterval: REFRESH });
    const { data: pnl } = useSWR("pnl", api.pnl, { refreshInterval: REFRESH });
    const { data: history } = useSWR("history", () => api.pnlHistory(), { refreshInterval: REFRESH });
    const { data: positions } = useSWR("positions", api.positions, { refreshInterval: REFRESH });
    const { data: fills } = useSWR("fills", () => api.fills(), { refreshInterval: REFRESH });

    return (
        <main className="p-6 space-y-6 max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold tracking-tight">
                AmalieTrader
                <span className="ml-3 text-sm font-normal text-gray-400">
                    {status?.account ?? "–"}
                </span>
            </h1>

            {/* System status banner */}
            <StatusBar status={status} />

            {/* PnL summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard label="Daily P&L" value={pnl?.daily_pnl} currency />
                <StatCard label="Unrealized" value={pnl?.unrealized_pnl} currency />
                <StatCard label="Realized" value={pnl?.realized_pnl} currency />
                <StatCard label="Net Liquidation" value={pnl?.net_liquidation} currency />
            </div>

            {/* PnL chart */}
            <section className="bg-gray-900 rounded-xl p-4">
                <h2 className="text-sm text-gray-400 mb-3">Daily P&L history</h2>
                <PnLChart data={history ?? []} />
            </section>

            {/* Positions + Fills side by side on large screens */}
            <div className="grid md:grid-cols-2 gap-6">
                <section className="bg-gray-900 rounded-xl p-4">
                    <h2 className="text-sm text-gray-400 mb-3">Open positions</h2>
                    <PositionsTable positions={positions ?? []} />
                </section>
                <section className="bg-gray-900 rounded-xl p-4">
                    <h2 className="text-sm text-gray-400 mb-3">Recent fills</h2>
                    <FillsTable fills={fills ?? []} />
                </section>
            </div>
        </main>
    );
}

function StatCard({ label, value, currency }: {
    label: string;
    value?: number | null;
    currency?: boolean;
}) {
    const fmt = (v: number) =>
        currency
            ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(v)
            : v.toFixed(2);

    const color =
        value == null ? "text-gray-400"
            : value > 0 ? "text-up"
                : value < 0 ? "text-down"
                    : "text-gray-400";

    return (
        <div className="bg-gray-900 rounded-xl p-4">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className={`text-xl font-semibold ${color}`}>
                {value == null ? "–" : fmt(value)}
            </p>
        </div>
    );
}
