"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

interface Trade {
    id: string;
    symbol: string;
    side: string;
    entry_price: number;
    exit_price: number | null;
    current_price?: number;
    pnl: number;
    result: string;
    created_at: string;
    volume?: number;
    status?: string;
}

export default function TradeHistoryPage() {
    const [trades, setTrades] = useState<Trade[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");
    const [closing, setClosing] = useState<string | null>(null);

    const fetchTrades = useCallback(async () => {
        try {
            const res = await api.get("/trades");
            setTrades(Array.isArray(res.data) ? res.data : []);
        } catch {
            // silently fail
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTrades();
        const interval = setInterval(fetchTrades, 15000);
        return () => clearInterval(interval);
    }, [fetchTrades]);

    // ── Computed stats from real data ──
    const openTrades = trades.filter(t => t.status === "open" || t.result === "OPEN");
    const closedTrades = trades.filter(t => t.status === "closed" || (t.result !== "OPEN" && t.status !== "open"));

    const filteredTrades = trades.filter(t => {
        if (filter === "all") return true;
        if (filter === "open") return t.status === "open" || t.result === "OPEN";
        if (filter === "closed") return t.status === "closed" || (t.result !== "OPEN" && t.status !== "open");
        if (filter === "wins") return t.result === "WIN";
        if (filter === "losses") return t.result === "LOSS";
        return true;
    });

    const wins = closedTrades.filter((t) => t.result === "WIN").length;
    const losses = closedTrades.filter((t) => t.result === "LOSS").length;
    const closedPnl = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
    const openPnl = openTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
    const totalPnl = closedPnl + openPnl;
    const avgWin = wins > 0 ? closedTrades.filter(t => t.result === "WIN").reduce((s, t) => s + t.pnl, 0) / wins : 0;
    const avgLoss = losses > 0 ? closedTrades.filter(t => t.result === "LOSS").reduce((s, t) => s + t.pnl, 0) / losses : 0;
    const profitFactor = losses > 0 && avgLoss !== 0
        ? (Math.abs(avgWin * wins) / Math.abs(avgLoss * losses)).toFixed(2)
        : "—";

    // ── Close position ──
    const closePosition = async (positionId: string) => {
        if (!confirm("Are you sure you want to close this position?")) return;
        setClosing(positionId);
        try {
            await api.post(`/positions/${positionId}/close`);
            fetchTrades();
        } catch (err) {
            console.error("Failed to close position", err);
            alert("Failed to close position. Check console for details.");
        } finally {
            setClosing(null);
        }
    };

    const closeAll = async () => {
        if (!confirm(`Close all ${openTrades.length} open positions?`)) return;
        try {
            await api.post("/positions/close-all");
            fetchTrades();
        } catch (err) {
            console.error("Failed to close all positions", err);
        }
    };

    // ── Build dynamic SVG from trade history ──
    const buildChartPath = () => {
        if (trades.length === 0) return { line: "", area: "" };

        const W = 800, H = 180;
        let cumPnl = 0;
        const sorted = [...trades]
            .filter(t => t.created_at)
            .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

        if (sorted.length === 0) return { line: "", area: "" };

        const points = sorted.map((t, i) => {
            cumPnl += t.pnl || 0;
            const x = sorted.length === 1 ? W / 2 : (i / (sorted.length - 1)) * W;
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
        const headers = ["Symbol", "Side", "Entry Price", "Exit/Current Price", "Volume", "PnL", "Status", "Date"];
        const rows = filteredTrades.map(t => [
            t.symbol,
            t.side,
            t.entry_price,
            t.exit_price || t.current_price || "",
            t.volume || 0.01,
            t.pnl?.toFixed(2) || "0.00",
            t.result || "OPEN",
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
                            <h2 className="text-lg font-bold text-on-surface">Cumulative Returns</h2>
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

                {/* Summary Cards */}
                <div className="lg:col-span-5 grid grid-cols-2 gap-3">
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-secondary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Open PnL</span>
                        <p className={`text-xl font-bold mt-2 ${openPnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {openPnl >= 0 ? "+" : ""}${fmt(Math.abs(openPnl))}
                        </p>
                    </div>
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-primary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Open Trades</span>
                        <p className="text-xl font-bold text-on-surface mt-2">{openTrades.length}</p>
                    </div>
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-secondary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Closed PnL</span>
                        <p className={`text-xl font-bold mt-2 ${closedPnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {closedPnl >= 0 ? "+" : ""}${fmt(Math.abs(closedPnl))}
                        </p>
                    </div>
                    <div className="bg-surface-container p-4 rounded-lg border-b-2 border-tertiary/10">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Profit Factor</span>
                        <p className="text-xl font-bold text-on-surface mt-2">{profitFactor}</p>
                    </div>
                </div>
            </div>

            {/* ─── Filter Bar + Actions ─── */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3 flex-wrap">
                    <select
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        className="bg-surface-container-high text-on-surface text-xs px-3 py-1.5 rounded border border-outline-variant/20 focus:outline-none"
                    >
                        <option value="all">All ({trades.length})</option>
                        <option value="open">Open ({openTrades.length})</option>
                        <option value="closed">Closed ({closedTrades.length})</option>
                        {wins > 0 && <option value="wins">Winners ({wins})</option>}
                        {losses > 0 && <option value="losses">Losers ({losses})</option>}
                    </select>
                    <span className="text-[10px] text-on-surface-variant">
                        {openTrades.length} open / {closedTrades.length} closed
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    {openTrades.length > 0 && (
                        <button
                            onClick={closeAll}
                            className="flex items-center gap-1 px-3 py-1.5 bg-tertiary-container text-on-tertiary-container text-[10px] font-bold uppercase tracking-wider rounded hover:opacity-90 transition-all"
                        >
                            <span className="material-symbols-outlined text-[14px]">close</span>
                            Close All ({openTrades.length})
                        </button>
                    )}
                    <button
                        onClick={exportCSV}
                        disabled={filteredTrades.length === 0}
                        className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high text-on-surface-variant text-[10px] font-bold uppercase tracking-wider rounded hover:bg-surface-container-highest transition-colors disabled:opacity-40"
                    >
                        <span className="material-symbols-outlined text-[16px]">download</span>
                        Export CSV
                    </button>
                </div>
            </div>

            {/* ─── Trades Table ─── */}
            <div className="bg-surface-container-low rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/10">
                                <th className="py-3 px-6 font-medium">Asset</th>
                                <th className="py-3 px-4 font-medium">Type</th>
                                <th className="py-3 px-4 font-medium">Entry</th>
                                <th className="py-3 px-4 font-medium">Exit / Current</th>
                                <th className="py-3 px-4 font-medium">Size</th>
                                <th className="py-3 px-4 font-medium text-right">P&L</th>
                                <th className="py-3 px-4 font-medium text-center">Status</th>
                                <th className="py-3 px-4 font-medium text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-outline-variant/5">
                            {filteredTrades.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="py-16 text-center text-sm text-on-surface-variant">
                                        {loading ? "Loading trade history..." : "No trades match your filter."}
                                    </td>
                                </tr>
                            ) : (
                                filteredTrades.map((t, i) => {
                                    const isOpen = t.status === "open" || t.result === "OPEN";
                                    const isBuy = t.side?.toUpperCase() === "BUY";
                                    const pnl = t.pnl || 0;
                                    const displayPrice = isOpen ? t.current_price : t.exit_price;

                                    return (
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
                                                    isBuy
                                                        ? "bg-secondary-container/20 text-secondary border-secondary/20"
                                                        : "bg-tertiary-container/20 text-tertiary border-tertiary/20"
                                                }`}>
                                                    {isBuy ? "LONG" : "SHORT"}
                                                </span>
                                            </td>
                                            <td className="py-4 px-4 text-sm font-mono text-on-surface">{t.entry_price || "—"}</td>
                                            <td className="py-4 px-4 text-sm font-mono text-on-surface">{displayPrice || "—"}</td>
                                            <td className="py-4 px-4 text-sm font-mono text-on-surface">{t.volume || 0.01}</td>
                                            <td className={`py-4 px-4 text-right text-sm font-mono font-bold ${
                                                pnl >= 0 ? "text-secondary" : "text-tertiary"
                                            }`}>
                                                {pnl >= 0 ? "+" : ""}${Math.abs(pnl).toFixed(2)}
                                            </td>
                                            <td className="py-4 px-4 text-center">
                                                <span className={`px-2 py-0.5 text-[9px] font-bold uppercase rounded-sm ${
                                                    isOpen
                                                        ? "bg-primary-container/30 text-primary"
                                                        : t.result === "WIN"
                                                            ? "text-secondary"
                                                            : "text-tertiary"
                                                }`}>
                                                    {isOpen ? "LIVE" : t.result || "CLOSED"}
                                                </span>
                                            </td>
                                            <td className="py-4 px-4 text-center">
                                                {isOpen ? (
                                                    <button
                                                        onClick={() => closePosition(t.id)}
                                                        disabled={closing === t.id}
                                                        className="text-on-surface-variant hover:text-tertiary transition-colors disabled:opacity-40"
                                                        title="Close position"
                                                    >
                                                        <span className="material-symbols-outlined text-[18px]">
                                                            {closing === t.id ? "hourglass_empty" : "close"}
                                                        </span>
                                                    </button>
                                                ) : (
                                                    <span className="text-[10px] text-on-surface-variant">—</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>

                {filteredTrades.length > 0 && (
                    <div className="p-4 border-t border-outline-variant/10 flex items-center justify-between">
                        <span className="text-[10px] text-on-surface-variant uppercase">
                            Showing {filteredTrades.length} of {trades.length} trades
                        </span>
                        <span className={`text-[10px] font-bold ${totalPnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            Total: {totalPnl >= 0 ? "+" : ""}${fmt(Math.abs(totalPnl))}
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
