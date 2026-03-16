"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";
import ConfirmModal from "@/components/ConfirmModal";

interface Position {
    id: string;
    symbol: string;
    side: string;
    type: string;
    entry: number;
    entry_price: number;
    sl: number;
    tp: number;
    volume?: number;
    current_price?: number;
    currentPrice?: number;
    pnl?: number;
    profit?: number;
}

export default function PositionsPage() {
    const [positions, setPositions] = useState<Position[]>([]);
    const [loading, setLoading] = useState(true);
    const [closing, setClosing] = useState<string | null>(null);
    const [confirmTarget, setConfirmTarget] = useState<Position | "all" | null>(null);
    const [error, setError] = useState<string | null>(null);

    const fetchPositions = useCallback(async () => {
        try {
            const res = await api.get("/positions");
            setPositions(Array.isArray(res.data) ? res.data : []);
        } catch {
            // silently fail
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPositions();
        const interval = setInterval(fetchPositions, 15000);
        return () => clearInterval(interval);
    }, [fetchPositions]);

    const totalExposure = positions.reduce((s, p) => s + (p.volume || 0.01), 0);
    const floatingPnl = positions.reduce((s, p) => s + (p.pnl ?? p.profit ?? 0), 0);
    const largestLoss = positions.length > 0
        ? Math.min(...positions.map(p => p.pnl ?? p.profit ?? 0), 0)
        : 0;

    const handleConfirmClose = async () => {
        setError(null);
        if (confirmTarget === "all") {
            setClosing("all");
            try {
                await api.post("/positions/close-all");
                setConfirmTarget(null);
                fetchPositions();
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
                fetchPositions();
            } catch (err) {
                console.error("Failed to close position", err);
                setError("Failed to close position. Please try again.");
            } finally {
                setClosing(null);
            }
        }
    };

    const fmt = (n: number) =>
        n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    return (
        <div className="flex flex-col gap-6">
            {/* ─── Top Stats — Now Live ─── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-surface-container p-4 rounded-lg border-b-2 border-primary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Total Exposure</span>
                    <p className="text-xl font-bold text-on-surface mt-2">
                        {positions.length > 0 ? `${totalExposure.toFixed(2)} lots` : "0.00 lots"}
                    </p>
                </div>
                <div className="bg-surface-container p-4 rounded-lg border-b-2 border-tertiary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Largest Loss</span>
                    <p className={`text-xl font-bold mt-2 ${largestLoss < 0 ? "text-tertiary" : "text-on-surface"}`}>
                        ${fmt(Math.abs(largestLoss))}
                    </p>
                </div>
                <div className="bg-surface-container p-4 rounded-lg border-b-2 border-secondary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Open Positions</span>
                    <div className="flex items-center gap-2 mt-2">
                        <span className="text-xl font-bold text-on-surface">{positions.length}</span>
                        {positions.length > 0 && (
                            <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>verified</span>
                        )}
                    </div>
                </div>
                <div className="bg-surface-container p-4 rounded-lg border-b-2 border-secondary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Floating PnL</span>
                    <p className={`text-xl font-bold mt-2 ${floatingPnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                        {floatingPnl >= 0 ? "+" : ""}${fmt(Math.abs(floatingPnl))}
                    </p>
                </div>
            </div>

            {/* ─── Active Positions Header ─── */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-lg font-bold text-on-surface">Active Positions</h2>
                    <span className="px-2 py-0.5 bg-surface-container-high rounded text-[10px] font-mono text-on-surface-variant">
                        {positions.length} OPEN
                    </span>
                    {loading && <span className="text-[10px] text-on-surface-variant animate-pulse">Updating…</span>}
                </div>
                {positions.length > 0 && (
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setConfirmTarget("all")}
                            className="px-3 py-1.5 bg-tertiary-container text-on-tertiary-container text-[10px] font-bold uppercase tracking-wider rounded hover:opacity-90 transition-all"
                        >
                            Close All Positions
                        </button>
                    </div>
                )}
            </div>

            {/* ─── Positions Table ─── */}
            <div className="bg-surface-container-low rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/10">
                                <th className="py-3 px-6 font-medium">Pair / ID</th>
                                <th className="py-3 px-4 font-medium">Side</th>
                                <th className="py-3 px-4 font-medium">Lot Size</th>
                                <th className="py-3 px-4 font-medium">Entry Price</th>
                                <th className="py-3 px-4 font-medium">Current Price</th>
                                <th className="py-3 px-4 font-medium text-right">PnL (USD)</th>
                                <th className="py-3 px-4 font-medium text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-outline-variant/5">
                            {positions.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="py-16 text-center text-sm text-on-surface-variant">
                                        {loading ? "Loading positions…" : "No active positions right now."}
                                    </td>
                                </tr>
                            ) : (
                                positions.map((p) => {
                                    const side = (p.side || p.type || "").toUpperCase();
                                    const isBuy = side.includes("BUY") || side === "LONG";
                                    const pnl = p.pnl ?? p.profit ?? 0;
                                    const entry = p.entry_price || p.entry || 0;
                                    const current = p.currentPrice || p.current_price || 0;

                                    return (
                                        <tr key={p.id} className="hover:bg-surface-container-high/50 transition-colors">
                                            <td className="py-4 px-6">
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-bold text-on-surface">{p.symbol}</span>
                                                    <span className="text-[10px] text-on-surface-variant font-mono">{p.id}</span>
                                                </div>
                                            </td>
                                            <td className="py-4 px-4">
                                                <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-sm border ${
                                                    isBuy
                                                        ? "bg-secondary-container/20 text-secondary border-secondary/20"
                                                        : "bg-tertiary-container/20 text-tertiary border-tertiary/20"
                                                }`}>
                                                    {isBuy ? "BUY" : "SELL"}
                                                </span>
                                            </td>
                                            <td className="py-4 px-4 text-sm font-mono text-on-surface">{p.volume || 0.01}</td>
                                            <td className="py-4 px-4 text-sm font-mono text-on-surface">{entry || "—"}</td>
                                            <td className="py-4 px-4 text-sm font-mono text-on-surface">{current || "—"}</td>
                                            <td className={`py-4 px-4 text-right text-sm font-mono font-bold ${
                                                pnl >= 0 ? "text-secondary" : "text-tertiary"
                                            }`}>
                                                {pnl >= 0 ? "+" : ""}${Math.abs(pnl).toFixed(2)}
                                            </td>
                                            <td className="py-4 px-4 text-center">
                                                <button
                                                    onClick={() => setConfirmTarget(p)}
                                                    disabled={closing === p.id}
                                                    className="text-on-surface-variant hover:text-tertiary transition-colors disabled:opacity-40"
                                                    title="Close position"
                                                >
                                                    <span className="material-symbols-outlined text-[18px]">
                                                        {closing === p.id ? "hourglass_empty" : "close"}
                                                    </span>
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* ─── Confirm Close Modal ─── */}
            <ConfirmModal
                open={confirmTarget !== null}
                title={
                    confirmTarget === "all"
                        ? "Close All Positions"
                        : `Close ${confirmTarget && confirmTarget !== "all" ? confirmTarget.symbol : ""} Position`
                }
                description={
                    confirmTarget === "all"
                        ? `This will close all ${positions.length} open position${positions.length !== 1 ? "s" : ""} at market price. This action cannot be undone.`
                        : "This position will be closed at the current market price. This action cannot be undone."
                }
                details={
                    confirmTarget && confirmTarget !== "all"
                        ? (() => {
                            const pnl = confirmTarget.pnl ?? confirmTarget.profit ?? 0;
                            const entry = confirmTarget.entry_price || confirmTarget.entry || 0;
                            const side = (confirmTarget.side || confirmTarget.type || "").toUpperCase();
                            const isBuy = side.includes("BUY") || side === "LONG";
                            return [
                                { label: "Symbol", value: confirmTarget.symbol },
                                { label: "Side", value: isBuy ? "BUY" : "SELL" },
                                { label: "Lot Size", value: `${confirmTarget.volume || 0.01}` },
                                { label: "Entry", value: entry ? `$${entry}` : "—" },
                                {
                                    label: "Floating PnL",
                                    value: `${pnl >= 0 ? "+" : ""}$${Math.abs(pnl).toFixed(2)}`,
                                    color: pnl >= 0 ? "text-secondary" : "text-tertiary",
                                },
                            ];
                        })()
                        : confirmTarget === "all"
                            ? [
                                { label: "Positions", value: `${positions.length}` },
                                { label: "Total Exposure", value: `${totalExposure.toFixed(2)} lots` },
                                {
                                    label: "Floating PnL",
                                    value: `${floatingPnl >= 0 ? "+" : ""}$${fmt(Math.abs(floatingPnl))}`,
                                    color: floatingPnl >= 0 ? "text-secondary" : "text-tertiary",
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
