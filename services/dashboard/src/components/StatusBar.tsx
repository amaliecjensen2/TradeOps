import type { SystemStatus } from "@/lib/api";

export default function StatusBar({ status }: { status?: SystemStatus }) {
    if (!status) return null;

    if (status.halted) {
        return (
            <div className="rounded-xl bg-down/20 border border-down px-4 py-3 text-down font-semibold">
                🛑 TRADING HALTED — {status.halt_reason}
            </div>
        );
    }

    if (!status.adapter_connected) {
        return (
            <div className="rounded-xl bg-warn/20 border border-warn px-4 py-3 text-warn font-semibold">
                ⚠️ IBKR connection lost — strategies paused
            </div>
        );
    }

    return (
        <div className="rounded-xl bg-up/10 border border-up/30 px-4 py-3 text-up text-sm">
            ✓ Connected — paper trading active
        </div>
    );
}
