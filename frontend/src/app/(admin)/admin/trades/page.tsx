"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";
import { formatIstDate, formatIstTime } from "@/utils/ist";

interface GlobalTrade {
    id: string;
    user: string;
    symbol: string;
    side: string;
    type: string;
    entry_price: number;
    exit_price: number | null;
    pnl: number | null;
    status: string;
    created_at: string;
}

export default function AdminTrades() {
    const [trades, setTrades] = useState<GlobalTrade[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");

    const fetchTrades = useCallback(async () => {
        try {
            const res = await api.get("/admin/trades");
            setTrades(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error("Failed to fetch trades", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTrades();
    }, [fetchTrades]);

    const filteredTrades = trades.filter((t) => {
        if (filter === "all") return true;
        if (filter === "open") return t.status === "open";
        if (filter === "closed") return t.status === "closed";
        return true;
    });

    return (
        <div className="flex flex-col gap-6">
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-on-surface">Global Trades</h1>
                    <p className="text-sm text-on-surface-variant">Real-time feed of all trades executed across the platform.</p>
                </div>
                <div className="flex bg-surface-container rounded-lg p-1">
                    {["all", "open", "closed"].map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-4 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all ${
                                filter === f 
                                    ? "bg-primary text-on-primary shadow-sm" 
                                    : "text-on-surface-variant hover:text-on-surface"
                            }`}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </header>

            <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/5">
                                <th className="py-4 px-6 font-medium">Trade Details</th>
                                <th className="py-4 px-6 font-medium">User</th>
                                <th className="py-4 px-6 font-medium">Entry/Exit</th>
                                <th className="py-4 px-6 font-medium">PnL</th>
                                <th className="py-4 px-6 font-medium text-right">Time</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-outline-variant/5">
                            {loading ? (
                                <tr>
                                    <td colSpan={5} className="py-12 text-center text-sm text-on-surface-variant">
                                        <div className="flex flex-col items-center gap-2">
                                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                            Syncing trade feed...
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredTrades.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="py-12 text-center text-sm text-on-surface-variant">
                                        No trades found for this filter.
                                    </td>
                                </tr>
                            ) : (
                                filteredTrades.map((t) => (
                                    <tr key={t.id} className="hover:bg-surface-container-high/30 transition-colors">
                                        <td className="py-4 px-6">
                                            <div className="flex items-center gap-3">
                                                <div className={`p-2 rounded-lg ${t.side === 'buy' ? 'bg-secondary/10 text-secondary' : 'bg-tertiary/10 text-tertiary'}`}>
                                                    <span className="material-symbols-outlined text-[20px]">
                                                        {t.side === 'buy' ? 'trending_up' : 'trending_down'}
                                                    </span>
                                                </div>
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-bold text-on-surface">{t.symbol}</span>
                                                    <span className="text-[10px] uppercase font-bold text-on-surface-variant">{t.side}</span>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6">
                                            <div className="flex flex-col">
                                                <span className="text-sm font-medium text-on-surface">{t.user.split('@')[0]}</span>
                                                <span className="text-[10px] text-on-surface-variant truncate max-w-[120px]">{t.user}</span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6">
                                            <div className="flex flex-col font-mono text-xs">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-on-surface-variant font-bold w-3">In</span>
                                                    <span className="text-on-surface">{t.entry_price.toFixed(5)}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-on-surface-variant font-bold w-3">Out</span>
                                                    <span className="text-on-surface">{t.exit_price?.toFixed(5) || "Pending"}</span>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6">
                                            <div className="flex flex-col">
                                                <span className={`text-sm font-bold ${ (t.pnl || 0) >= 0 ? "text-secondary" : "text-tertiary"}`}>
                                                    {t.pnl ? `${t.pnl > 0 ? "+" : ""}${t.pnl.toFixed(2)}` : "-"}
                                                </span>
                                                <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase w-fit ${
                                                    t.status === 'closed' ? 'bg-surface-container-highest text-on-surface-variant' : 'bg-primary/20 text-primary animate-pulse'
                                                }`}>
                                                    {t.status}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6 text-right">
                                            <div className="flex flex-col items-end whitespace-nowrap">
                                                <span className="text-xs text-on-surface font-medium">
                                                    {formatIstDate(t.created_at)}
                                                </span>
                                                <span className="text-[10px] text-on-surface-variant font-mono">
                                                    {formatIstTime(t.created_at).slice(0, 5)}
                                                </span>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
