"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import api from "@/services/api";
import PerformanceChart from "@/components/PerformanceChart";
import ConfirmModal from "@/components/ConfirmModal";
import TradeDetailModal from "@/components/TradeDetailModal";

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
    execution_time?: string;
    close_time?: string;
    execution_latency_ms?: number | null;
    signal_time?: string | null;
    reject_reason?: string | null;
    volume?: number;
    status?: string;
    commission?: number;
    swap?: number;
    deal_id?: string;
    broker_time?: string;
    source?: string;
}

export default function TradeHistoryPage() {
    const [trades, setTrades] = useState<Trade[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");
    const [closing, setClosing] = useState<string | null>(null);
    const [confirmTarget, setConfirmTarget] = useState<Trade | "all" | null>(null);
    const [detailTrade, setDetailTrade] = useState<Trade | null>(null);
    const [error, setError] = useState<string | null>(null);

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

    const getStatusColor = (result: string, status: string, pnl: number) => {
        if (status === "open") return "text-primary";
        if (result === "WIN") return "text-secondary";
        if (result === "LOSS" || result === "FAILED") return "text-tertiary";
        return "text-on-surface-variant";
    };

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

    // ── Close position (via modal) ──
    const handleConfirmClose = async () => {
        setError(null);
        if (confirmTarget === "all") {
            setClosing("all");
            try {
                await api.post("/positions/close-all");
                setConfirmTarget(null);
                fetchTrades();
            } catch (err) {
                console.error("Failed to close all positions", err);
                setError("Failed to close all positions. Please try again.");
            } finally {
                setClosing(null);
            }
        } else if (confirmTarget) {
            setClosing(confirmTarget.id);
            try {
                await api.post(`/positions/${confirmTarget.id}/close`);
                setConfirmTarget(null);
                fetchTrades();
            } catch (err) {
                console.error("Failed to close position", err);
                setError("Failed to close position. Please try again.");
            } finally {
                setClosing(null);
            }
        }
    };

    // ── Build equity curve data from trade history ──
    const equityCurveData = useMemo(() => {
        const sorted = [...trades]
            .filter(t => t.created_at)
            .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        let cumPnl = 0;
        return sorted.map(t => {
            cumPnl += t.pnl || 0;
            return { time: t.created_at, pnl: cumPnl };
        });
    }, [trades]);

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
                    <PerformanceChart
                        data={equityCurveData}
                        height={180}
                        showReferenceLine={false}
                        loading={loading}
                    />
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
                            onClick={() => setConfirmTarget("all")}
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
                                                    <span className="text-[10px] text-on-surface-variant font-mono whitespace-nowrap">
                                                        {(() => {
                                                            const d = t.execution_time || t.created_at;
                                                            if (!d) return "—";
                                                            const date = new Date(d);
                                                            return `${date.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" })} • ${date.toLocaleTimeString("en-GB", { hour12: false, timeZone: "Asia/Kolkata" })}`;
                                                        })()}
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
                                                        onClick={() => setConfirmTarget(t)}
                                                        disabled={closing === t.id}
                                                        className="text-on-surface-variant hover:text-tertiary transition-colors disabled:opacity-40"
                                                        title="Close position"
                                                    >
                                                        <span className="material-symbols-outlined text-[18px]">
                                                            {closing === t.id ? "hourglass_empty" : "close"}
                                                        </span>
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() => setDetailTrade(t)}
                                                        className="text-on-surface-variant hover:text-primary transition-colors"
                                                        title="View details"
                                                    >
                                                        <span className="material-symbols-outlined text-[18px]">visibility</span>
                                                    </button>
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

            {/* ─── Confirm Close Modal ─── */}
            <ConfirmModal
                open={confirmTarget !== null}
                title={
                    confirmTarget === "all"
                        ? "Close All Positions"
                        : `Close ${confirmTarget ? confirmTarget.symbol : ""} Position`
                }
                description={
                    confirmTarget === "all"
                        ? `This will close all ${openTrades.length} open position${openTrades.length !== 1 ? "s" : ""} at market price. This action cannot be undone.`
                        : "This position will be closed at the current market price. This action cannot be undone."
                }
                details={
                    confirmTarget === "all"
                        ? [
                                { label: "Positions", value: `${openTrades.length}` },
                                {
                                    label: "Floating PnL",
                                    value: `${openPnl >= 0 ? "+" : ""}$${fmt(Math.abs(openPnl))}`,
                                    color: openPnl >= 0 ? "text-secondary" : "text-tertiary",
                                },
                            ]
                        : confirmTarget
                            ? [
                                { label: "Symbol", value: confirmTarget.symbol },
                                { label: "Side", value: confirmTarget.side?.toUpperCase() === "BUY" ? "LONG" : "SHORT" },
                                { label: "Entry", value: `$${confirmTarget.entry_price || "—"}` },
                                {
                                    label: "Current PnL",
                                    value: `${(confirmTarget.pnl || 0) >= 0 ? "+" : ""}$${Math.abs(confirmTarget.pnl || 0).toFixed(2)}`,
                                    color: (confirmTarget.pnl || 0) >= 0 ? "text-secondary" : "text-tertiary",
                                },
                            ]
                            : undefined
                }
                confirmLabel={confirmTarget === "all" ? "Close All" : "Close Position"}
                variant="danger"
                loading={closing !== null}
                onConfirm={handleConfirmClose}
                onCancel={() => { setConfirmTarget(null); setError(null); }}
            />

            {/* ─── Trade Detail Modal ─── */}
            <TradeDetailModal
                open={detailTrade !== null}
                trade={detailTrade}
                onClose={() => setDetailTrade(null)}
            />

            {/* ─── Error Toast ─── */}
            {error && (
                <div className="fixed bottom-6 right-6 z-50 bg-tertiary text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-[scaleIn_200ms_ease-out]">
                    <span className="material-symbols-outlined text-lg">error</span>
                    <span className="text-sm font-medium">{error}</span>
                    <button onClick={() => setError(null)} className="ml-2 hover:opacity-70 transition-opacity">
                        <span className="material-symbols-outlined text-sm">close</span>
                    </button>
                </div>
            )}
        </div>
    );
}
