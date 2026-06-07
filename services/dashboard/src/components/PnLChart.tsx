"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import type { PnLSnapshot } from "@/lib/api";

interface Props { data: PnLSnapshot[] }

export default function PnLChart({ data }: Props) {
    if (data.length === 0) {
        return <p className="text-gray-500 text-sm">No data yet</p>;
    }

    // Vend om så ældste er til venstre
    const chartData = [...data].reverse().map((d) => ({
        time: new Date(d.timestamp).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
        pnl: d.daily_pnl,
    }));

    return (
        <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
                <XAxis dataKey="time" tick={{ fill: "#9ca3af", fontSize: 11 }} minTickGap={40} />
                <YAxis
                    tick={{ fill: "#9ca3af", fontSize: 11 }}
                    tickFormatter={(v) => `$${v.toLocaleString()}`}
                    width={70}
                />
                <Tooltip
                    contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                    formatter={(v: number) => [`$${v.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, "Daily P&L"]}
                />
                <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 2" />
                <Line
                    type="monotone"
                    dataKey="pnl"
                    dot={false}
                    stroke="#22c55e"
                    strokeWidth={2}
                    activeDot={{ r: 4 }}
                />
            </LineChart>
        </ResponsiveContainer>
    );
}
