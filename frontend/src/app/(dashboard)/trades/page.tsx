"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";

interface Trade {
    id: string;
    symbol: string;
    side: string;
    entry_price: number;
    exit_price: number;
    pnl: number;
    result: string;
    created_at: string;
    volume?: number;
}

export default function TradeHistoryPage() {
    const [trades, setTrades] = useState<Trade[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");

    useEffect(() => {
        api.get("/trades")
            .then((res) => setTrades(Array.isArray(res.data) ? res.data : []))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    // ── Computed stats from real data ──
    const filteredTrades = trades.filter(t => {
        if (filter === "all") return true;
        if (filter === "wins") return t.result === "WIN";
        if (filter === "losses") return t.result === "LOSS";
        return true;
    });

    const wins = trades.filter((t) => t.result === "WIN").length;
    const losses = trades.filter((t) => t.result === "LOSS").length;
    const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
    const avgWin = wins > 0 ? trades.filter(t => t.result === "WIN").reduce((s, t) => s + t.pnl, 0) / wins : 0;
    const avgLoss = losses > 0 ? trades.filter(t => t.result === "LOSS").reduce((s, t) => s + t.pnl, 0) / losses : 0;
    const profitFactor = losses > 0 && avgLoss !== 0
        ? (Math.abs(avgWin * wins) / Math.abs(avgLoss * losses)).toFixed(2)
        : "—";

    // ── Build dynamic SVG from trade history ──
    const buildChartPath = () => {
        if (trades.length === 0) return { line: "", area: "" };

        const W = 800, H = 180;
        let cumPnl = 0;
        const points = trades
            .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
            .map((t, i) => {
                cumPnl += t.pnl || 0;
                const x = trades.length === 1 ? W / 2 : (i / (trades.length - 1)) * W;
                return { x, pnl: cumPnl };
            });

        const min = Math.min(...points.map(p => p.pnl));
        const max = Math.max(...points.map(p => p.pnl));
        const range = max - min || 1;

        const mapped = points.map(p => ({
            x: p.x,
            y: H - 20 - ((p.pnl - min) / range) * (H - 40),
        }));

        if (mapped.length === 1) {
            return {
                line: `M${mapped[0].x - 50},${mapped[0].y} L${mapped[0].x + 50},${mapped[0].y}`,
                area: `M${mapped[0].x - 50},${mapped[0].y} L${mapped[0].x + 50},${mapped[0].y} L${mapped[0].x + 50},${H} L${mapped[0].x - 50},${H} Z`,
            };
        }

        let path = `M${mapped[0].x},${mapped[0].y}`;
        for (let i = 1; i < mapped.length; i++) {
            const cpx = (mapped[i - 1].x + mapped[i].x) / 2;
            path += ` C${cpx},${mapped[i - 1].y} ${cpx},${mapped[i].y} ${mapped[i].x},${mapped[i].y}`;
        }

        const last = mapped[mapped.length - 1];
        const area = path + ` L${last.x},${H} L${mapped[0].x},${H} Z`;
        return { line: path, area };
    };

    // ── CSV Export ──
    const exportCSV = () => {
        if (filteredTrades.length === 0) return;
        const headers = ["Symbol", "Side", "Entry Price", "Exit Price", "PnL", "Result", "Date"];
        const rows = filteredTrades.map(t => [
            t.symbol,
            t.side,
            t.entry_price,
            t.exit_price || "",
            t.pnl?.toFixed(2) || "0.00",
            t.result || "CLOSED",
            t.created_at,
        ]);
        const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `trade_history_${new Date().toISOString().split("T")[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const chart = buildChartPath();
    const fmt = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    return (
        <div className="flex flex-col gap-6">
            {/* ─── Top: Equity Curve + Summary Cards ─── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Dynamic Equity Curve */}
                <div className="lg:col-span-7 bg-surface-container-low rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Equity Curve</p>
                            <h2 className="text-lg font-bold text-on-surface">Cumulative Historical Returns</h2>
                        </div>
                        <span className={`text-sm font-bold ${totalPnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {totalPnl >= 0 ? "+" : ""}{fmt(totalPnl)}
                        </span>
                    </div>
                    <div className="h-[180px] relative">
                        <svg className="w-full h-full" viewBox="0 0 800 180" preserveAspectRatio="none">
                            <defs>
                                <linearGradient id="histGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor={totalPnl >= 0 ? "#4edea3" : "#ffb3b0"} stopOpacity="0.15" />
                                    <stop offset="100%" stopColor={totalPnl >= 0 ? "#4edea3" : "#ffb3b0"} stopOpacity="0" />
                                </linearGradient>
                            </defs>
                            {chart.area && <path d={chart.area} fill="url(#histGradient)" />}
                            {chart.line && <path d={chart.line} fill="none" stroke={totalPnl >= 0 ? "#4edea3" : "#ffb3b0"} strokeWidth="2" strokeLinecap="round" />}
                        </svg>
                        {trades.length === 0 && !loading && (
                            <div className="absolute inset-0 flex items-center justify-center">
                                <span className="text-sm text-on-surface-variant">No trade data to chart</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Summary Cards — from real data */}
                <div className="lg:col-span-5 grid grid-cols-2 gap-3">
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-secondary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Total Net Profit</span>
                        <p className={`text-xl font-bold mt-2 ${totalPnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {totalPnl >= 0 ? "+" : ""}${fmt(Math.abs(totalPnl))}
                        </p>
                    </div>
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-primary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Profit Factor</span>
                        <p className="text-xl font-bold text-on-surface mt-2">{profitFactor}</p>
                    </div>
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-secondary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Avg Winner</span>
                        <p className="text-xl font-bold text-secondary mt-2">+${fmt(Math.abs(avgWin))}</p>
                    </div>
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-tertiary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Avg Loser</span>
                        <p className="text-xl font-bold text-tertiary mt-2">-${fmt(Math.abs(avgLoss))}</p>
                    </div>
                </div>
            </div>

            {/* ─── Filter Bar — Functional ─── */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3 flex-wrap">
                    <select
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        className="bg-surface-container-high text-on-surface text-xs px-3 py-1.5 rounded border border-outline-variant/20 focus:outline-none"
                    >
                        <option value="all">All Trades ({trades.length})</option>
                        <option value="wins">Winners ({wins})</option>
                        <option value="losses">Losers ({losses})</option>
                    </select>
                    <span className="text-[10px] text-on-surface-variant">
                        W/L: {wins}/{losses} ({trades.length > 0 ? ((wins / trades.length) * 100).toFixed(1) : 0}%)
                    </span>
                </div>
                <button
                    onClick={exportCSV}
                    disabled={filteredTrades.length === 0}
                    className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high text-on-surface-variant text-[10px] font-bold uppercase tracking-wider rounded hover:bg-surface-container-highest transition-colors disabled:opacity-40"
                >
                    <span className="material-symbols-outlined text-[16px]">download</span>
                    Export CSV ({filteredTrades.length})
                </button>
            </div>

            {/* ─── Trades Table ─── */}
            <div className="bg-surface-container-low rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/10">
                                <th className="py-3 px-6 font-medium">Asset / Strategy</th>
                                <th className="py-3 px-4 font-medium">Type</th>
                                <th className="py-3 px-4 font-medium">Entry Price</th>
                                <th className="py-3 px-4 font-medium">Exit Price</th>
                                <th className="py-3 px-4 font-medium">Size</th>
                                <th className="py-3 px-4 font-medium text-right">P&L ($)</th>
                                <th className="py-3 px-4 font-medium text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-outline-variant/5">
                            {filteredTrades.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="py-16 text-center text-sm text-on-surface-variant">
                                        {loading ? "Loading trade history…" : "No trades match your filter."}
                                    </td>
                                </tr>
                            ) : (
                                filteredTrades.map((t, i) => (
                                    <tr key={t.id || i} className="hover:bg-surface-container-high/50 transition-colors">
                                        <td className="py-4 px-6">
                                            <div className="flex flex-col">
                                                <span className="text-sm font-bold text-on-surface">{t.symbol}</span>
                                                <span className="text-[10px] text-on-surface-variant font-mono">
                                                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-4">
                                            <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-sm border ${
                                                t.side?.toUpperCase() === "BUY"
                                                    ? "bg-secondary-container/20 text-secondary border-secondary/20"
                                                    : "bg-tertiary-container/20 text-tertiary border-tertiary/20"
                                            }`}>
                                                {t.side?.toUpperCase() === "BUY" ? "LONG" : "SHORT"}
                                            </span>
                                        </td>
                                        <td className="py-4 px-4 text-sm font-mono text-on-surface">{t.entry_price || "—"}</td>
                                        <td className="py-4 px-4 text-sm font-mono text-on-surface">{t.exit_price || "—"}</td>
                                        <td className="py-4 px-4 text-sm font-mono text-on-surface">{t.volume || 0.01}</td>
                                        <td className={`py-4 px-4 text-right text-sm font-mono font-bold ${
                                            (t.pnl || 0) >= 0 ? "text-secondary" : "text-tertiary"
                                        }`}>
                                            {(t.pnl || 0) >= 0 ? "+" : ""}${(t.pnl || 0).toFixed(2)}
                                        </td>
                                        <td className="py-4 px-4 text-center">
                                            <span className={`text-[9px] font-bold uppercase ${t.result === "WIN" ? "text-secondary" : "text-tertiary"}`}>
                                                {t.result || "CLOSED"}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {filteredTrades.length > 0 && (
                    <div className="p-4 border-t border-outline-variant/10 flex items-center justify-between">
                        <span className="text-[10px] text-on-surface-variant uppercase">
                            Showing {filteredTrades.length} of {trades.length} trades
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
