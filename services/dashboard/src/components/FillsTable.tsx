import type { Fill } from "@/lib/api";

export default function FillsTable({ fills }: { fills: Fill[] }) {
    if (fills.length === 0)
        return <p className="text-gray-500 text-sm">No fills yet</p>;

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-gray-500 text-xs border-b border-gray-800">
                        <th className="text-left pb-2">Time</th>
                        <th className="text-left pb-2">Symbol</th>
                        <th className="text-left pb-2">Side</th>
                        <th className="text-right pb-2">Qty</th>
                        <th className="text-right pb-2">Price</th>
                        <th className="text-right pb-2">Commission</th>
                    </tr>
                </thead>
                <tbody>
                    {fills.map((f) => (
                        <tr key={f.exec_id} className="border-b border-gray-800/50">
                            <td className="py-2 text-gray-400 text-xs">
                                {new Date(f.timestamp).toLocaleTimeString()}
                            </td>
                            <td className="py-2 font-semibold">{f.symbol}</td>
                            <td className={`py-2 font-medium ${f.side === "BUY" ? "text-up" : "text-down"}`}>
                                {f.side}
                            </td>
                            <td className="py-2 text-right">{f.quantity}</td>
                            <td className="py-2 text-right">${f.price.toFixed(2)}</td>
                            <td className="py-2 text-right text-gray-400">
                                {f.commission != null ? `$${f.commission.toFixed(2)}` : "–"}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
