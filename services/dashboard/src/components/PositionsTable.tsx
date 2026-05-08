import type { Position } from "@/lib/api";

export default function PositionsTable({ positions }: { positions: Position[] }) {
    if (positions.length === 0)
        return <p className="text-gray-500 text-sm">No open positions</p>;

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-gray-500 text-xs border-b border-gray-800">
                        <th className="text-left pb-2">Symbol</th>
                        <th className="text-right pb-2">Qty</th>
                        <th className="text-right pb-2">Avg Cost</th>
                        <th className="text-right pb-2">Market</th>
                        <th className="text-right pb-2">Value</th>
                    </tr>
                </thead>
                <tbody>
                    {positions.map((p) => {
                        const pnl = p.market_value != null && p.avg_cost != null
                            ? p.market_value - p.avg_cost * Math.abs(p.position) : null;
                        return (
                            <tr key={p.symbol} className="border-b border-gray-800/50">
                                <td className="py-2 font-semibold">{p.symbol}</td>
                                <td className={`py-2 text-right ${p.position >= 0 ? "text-up" : "text-down"}`}>
                                    {p.position}
                                </td>
                                <td className="py-2 text-right text-gray-300">${p.avg_cost.toFixed(2)}</td>
                                <td className="py-2 text-right text-gray-300">
                                    {p.market_price != null ? `$${p.market_price.toFixed(2)}` : "–"}
                                </td>
                                <td className={`py-2 text-right font-medium ${pnl == null ? "" : pnl >= 0 ? "text-up" : "text-down"}`}>
                                    {pnl != null ? `$${pnl.toFixed(2)}` : "–"}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
