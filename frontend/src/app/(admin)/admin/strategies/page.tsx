"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

interface StrategyStat {
    strategy_slug: string;
    total_trades: number;
    total_pnl: number;
    win_rate: number;
    last_updated: string;
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
    }, [fetchStats]);

    return (
        <div className="flex flex-col gap-6">
            <header>
                <h1 className="text-2xl font-bold text-on-surface">Strategy Performance</h1>
                <p className="text-sm text-on-surface-variant">Aggregated analytics across all trading algorithms.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {loading ? (
                    [1,2,3].map(i => (
                        <div key={i} className="bg-surface-container-low h-48 rounded-xl animate-pulse"></div>
                    ))
                ) : stats.length === 0 ? (
                    <div className="col-span-full py-12 text-center bg-surface-container-low rounded-xl text-on-surface-variant">
                        No strategy statistics available yet.
                    </div>
                ) : (
                    stats.map((s) => (
                        <div key={s.strategy_slug} className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 flex flex-col justify-between">
                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <h3 className="text-lg font-bold text-on-surface capitalize">{s.strategy_slug.replace(/-/g, ' ')}</h3>
                                    <span className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">{s.strategy_slug}</span>
                                </div>
                                <div className={`px-4 py-2 rounded-lg text-sm font-bold ${s.total_pnl >= 0 ? "bg-secondary/10 text-secondary" : "bg-tertiary/10 text-tertiary"}`}>
                                    {s.total_pnl >= 0 ? "+" : ""}{s.total_pnl.toFixed(2)}
                                </div>
                            </div>
                            
                            <div className="grid grid-cols-2 gap-4 my-4">
                                <div className="bg-surface-container rounded-lg p-3">
                                    <div className="text-[10px] text-on-surface-variant uppercase font-bold">Win Rate</div>
                                    <div className="text-xl font-bold text-on-surface mt-1">{s.win_rate}%</div>
                                </div>
                                <div className="bg-surface-container rounded-lg p-3">
                                    <div className="text-[10px] text-on-surface-variant uppercase font-bold">Total Trades</div>
                                    <div className="text-xl font-bold text-on-surface mt-1">{s.total_trades}</div>
                                </div>
                            </div>

                            <div className="mt-auto pt-4 border-t border-outline-variant/5 flex justify-between items-center">
                                <span className="text-[9px] text-on-surface-variant italic">Last active: {new Date(s.last_updated).toLocaleString()}</span>
                                <span className="material-symbols-outlined text-primary text-lg">analytics</span>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
