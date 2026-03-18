"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

interface StrategyStat {
    bot_slug: string;
    bot_name: string;
    is_active: boolean;
    total_trades: number;
    total_pnl: number;
    wins: number;
    losses: number;
    open_trades: number;
    running_pnl: number;
    last_updated?: string | null;
}

export default function AdminStrategies() {
    const [stats, setStats] = useState<StrategyStat[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchStats = useCallback(async () => {
        try {
            const res = await api.get("/admin/strategies");
            setStats(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error("Failed to fetch strategy stats", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStats();
        // Auto-refresh every 30s to keep live data current
        const interval = setInterval(fetchStats, 30_000);
        return () => clearInterval(interval);
    }, [fetchStats]);

    return (
        <div className="flex flex-col gap-6">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-on-surface">Strategy Performance</h1>
                    <p className="text-sm text-on-surface-variant">Aggregated analytics across all trading algorithms.</p>
                </div>
                <button
                    onClick={fetchStats}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-low text-on-surface-variant text-sm hover:bg-surface-container transition-colors"
                >
                    <span className="material-symbols-outlined text-base">refresh</span>
                    Refresh
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {loading ? (
                    [1, 2, 3].map(i => (
                        <div key={i} className="bg-surface-container-low h-56 rounded-xl animate-pulse" />
                    ))
                ) : stats.length === 0 ? (
                    <div className="col-span-full py-12 text-center bg-surface-container-low rounded-xl text-on-surface-variant">
                        No active strategies found. Create a bot first.
                    </div>
                ) : (
                    stats.map((s) => {
                        const winRate = s.total_trades > 0
                            ? ((s.wins / s.total_trades) * 100).toFixed(1)
                            : "0";
                        const isRunning = s.open_trades > 0;
                        const closedPnlPositive = (s.total_pnl || 0) >= 0;
                        const runningPnlPositive = (s.running_pnl || 0) >= 0;

                        return (
                            <div key={s.bot_slug} className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 flex flex-col justify-between">

                                {/* Header: Name + Status Badge */}
                                <div className="flex justify-between items-start mb-4">
                                    <div>
                                        <h3 className="text-lg font-bold text-on-surface">{s.bot_name}</h3>
                                        <span className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">{s.bot_slug}</span>
                                    </div>
                                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${isRunning ? "bg-secondary/15 text-secondary" : "bg-outline-variant/20 text-on-surface-variant"}`}>
                                        {isRunning ? "● Running" : "○ Idle"}
                                    </span>
                                </div>

                                {/* Stats Grid */}
                                <div className="grid grid-cols-2 gap-3 my-3">
                                    <div className="bg-surface-container rounded-lg p-3">
                                        <div className="text-[10px] text-on-surface-variant uppercase font-bold">Win Rate</div>
                                        <div className="text-xl font-bold text-on-surface mt-1">{winRate}%</div>
                                    </div>
                                    <div className="bg-surface-container rounded-lg p-3">
                                        <div className="text-[10px] text-on-surface-variant uppercase font-bold">Total Trades</div>
                                        <div className="text-xl font-bold text-on-surface mt-1">{s.total_trades}</div>
                                    </div>
                                    <div className="bg-surface-container rounded-lg p-3">
                                        <div className="text-[10px] text-on-surface-variant uppercase font-bold">Closed PnL</div>
                                        <div className={`text-lg font-bold mt-1 ${closedPnlPositive ? "text-secondary" : "text-tertiary"}`}>
                                            {closedPnlPositive ? "+" : ""}{(s.total_pnl || 0).toFixed(2)}
                                        </div>
                                    </div>
                                    <div className="bg-surface-container rounded-lg p-3">
                                        <div className="text-[10px] text-on-surface-variant uppercase font-bold">
                                            Live PnL
                                            {isRunning && <span className="ml-1 text-secondary">({s.open_trades} open)</span>}
                                        </div>
                                        <div className={`text-lg font-bold mt-1 ${runningPnlPositive ? "text-secondary" : "text-tertiary"}`}>
                                            {isRunning
                                                ? `${runningPnlPositive ? "+" : ""}${(s.running_pnl || 0).toFixed(2)}`
                                                : <span className="text-on-surface-variant text-sm font-normal">No open trades</span>
                                            }
                                        </div>
                                    </div>
                                </div>

                                {/* Footer */}
                                <div className="mt-auto pt-4 border-t border-outline-variant/5 flex justify-between items-center">
                                    <span className="text-[9px] text-on-surface-variant italic">
                                        Last closed: {s.last_updated ? new Date(s.last_updated).toLocaleString() : "No closed trades yet"}
                                    </span>
                                    <span className="material-symbols-outlined text-primary text-lg">analytics</span>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
