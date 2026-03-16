"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";
import Link from "next/link";

interface SystemStatus {
    health: {
        redis: string;
        metaapi: string;
        trading_engine: string;
    };
    counters: {
        signals_today: number;
        trades_today: number;
    };
    observability: {
        total_users: number;
        active_mt_users: number;
        trading_enabled: boolean;
    };
}

interface PlanDetail {
    id: string;
    name: string;
    price: number;
    users: number;
    monthly_revenue: number;
}

interface GlobalTrade {
    id: string;
    user: string;
    symbol: string;
    side: string;
    entry_price: number;
    exit_price: number;
    pnl: number;
    status: string;
    created_at: string;
}

export default function AdminOverview() {
    const [system, setSystem] = useState<SystemStatus | null>(null);
    const [plans, setPlans] = useState<PlanDetail[]>([]);
    const [recentTrades, setRecentTrades] = useState<GlobalTrade[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [sysRes, planRes, tradeRes] = await Promise.allSettled([
                api.get("/admin/system"),
                api.get("/admin/plans"),
                api.get("/admin/trades"),
            ]);

            if (sysRes.status === "fulfilled") setSystem(sysRes.value.data);
            if (planRes.status === "fulfilled") setPlans(planRes.value.data);
            if (tradeRes.status === "fulfilled") setRecentTrades(tradeRes.value.data.slice(0, 5));
        } catch (err) {
            console.error("Admin dashboard fetch failed", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const totalRevenue = plans.reduce((acc, p) => acc + p.monthly_revenue, 0);

    return (
        <div className="flex flex-col gap-6">
            <header className="flex flex-col gap-1">
                <h1 className="text-2xl font-bold text-on-surface">Admin Overview</h1>
                <p className="text-sm text-on-surface-variant">Real-time platform performance and health.</p>
            </header>

            {/* Health & Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-surface-container p-5 rounded-xl border-l-4 border-primary">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Total Users</span>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-on-surface">{system?.observability.total_users || 0}</span>
                        <span className="text-[10px] text-primary font-bold">REG</span>
                    </div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border-l-4 border-secondary">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Active MT5</span>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-on-surface">{system?.observability.active_mt_users || 0}</span>
                        <span className="text-[10px] text-secondary font-bold">CONNECTED</span>
                    </div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border-l-4 border-tertiary">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Est. MRR</span>
                    <div className="mt-2 flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-on-surface">${totalRevenue.toLocaleString()}</span>
                        <span className="text-[10px] text-tertiary font-bold">USD</span>
                    </div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border-l-4 border-secondary">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Trading Engine</span>
                    <div className="mt-2 flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full animate-pulse ${system?.observability.trading_enabled ? "bg-secondary" : "bg-tertiary"}`}></div>
                        <span className={`text-lg font-bold ${system?.observability.trading_enabled ? "text-secondary" : "text-tertiary"}`}>
                            {system?.observability.trading_enabled ? "ACTIVE" : "HALTED"}
                        </span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Daily Activity */}
                <div className="lg:col-span-8 flex flex-col gap-6">
                    <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
                        <h2 className="text-lg font-bold text-on-surface mb-6">Activity Today</h2>
                        <div className="grid grid-cols-2 gap-6">
                            <div className="bg-surface-container-high rounded-lg p-5 flex items-center justify-between">
                                <div>
                                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Signals Ingested</span>
                                    <div className="text-3xl font-bold text-on-surface mt-1">{system?.counters.signals_today || 0}</div>
                                </div>
                                <span className="material-symbols-outlined text-primary text-4xl opacity-50">rss_feed</span>
                            </div>
                            <div className="bg-surface-container-high rounded-lg p-5 flex items-center justify-between">
                                <div>
                                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Trades Executed</span>
                                    <div className="text-3xl font-bold text-on-surface mt-1">{system?.counters.trades_today || 0}</div>
                                </div>
                                <span className="material-symbols-outlined text-secondary text-4xl opacity-50">show_chart</span>
                            </div>
                        </div>
                    </div>

                    {/* Latest Global Trades */}
                    <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
                        <div className="p-6 border-b border-outline-variant/10 flex items-center justify-between">
                            <h2 className="text-sm font-bold uppercase tracking-wider text-on-surface">Global Trade Feed</h2>
                            <Link href="/admin/trades" className="text-xs text-primary font-bold hover:underline">View All</Link>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/5">
                                        <th className="py-4 px-6 font-medium">User</th>
                                        <th className="py-4 px-6 font-medium">Symbol</th>
                                        <th className="py-4 px-6 font-medium">PnL</th>
                                        <th className="py-4 px-6 font-medium text-right">Time</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-outline-variant/5">
                                    {recentTrades.map((t) => (
                                        <tr key={t.id} className="hover:bg-surface-container-high/30 transition-colors">
                                            <td className="py-4 px-6">
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-bold text-on-surface">{t.user.split('@')[0]}</span>
                                                    <span className="text-[10px] text-on-surface-variant">{t.user}</span>
                                                </div>
                                            </td>
                                            <td className="py-4 px-6">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-bold">{t.symbol}</span>
                                                    <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-sm ${t.side === 'buy' ? 'bg-secondary/10 text-secondary' : 'bg-tertiary/10 text-tertiary'}`}>
                                                        {t.side.toUpperCase()}
                                                    </span>
                                                </div>
                                            </td>
                                            <td className={`py-4 px-6 text-sm font-mono font-bold ${t.pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                                                {t.pnl ? `${t.pnl > 0 ? "+" : ""}${t.pnl.toFixed(2)}` : "-"}
                                            </td>
                                            <td className="py-4 px-6 text-right text-[10px] text-on-surface-variant font-mono">
                                                {new Date(t.created_at).toLocaleTimeString()}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Subscriptions Breakout */}
                <div className="lg:col-span-4 flex flex-col gap-6">
                    <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
                        <h2 className="text-sm font-bold uppercase tracking-wider text-on-surface mb-6">Plan Distribution</h2>
                        <div className="space-y-6">
                            {plans.map((p) => (
                                <div key={p.id}>
                                    <div className="flex justify-between items-end mb-2">
                                        <div>
                                            <div className="text-sm font-bold text-on-surface">{p.name}</div>
                                            <div className="text-[10px] text-on-surface-variant">{p.users} active subscribers</div>
                                        </div>
                                        <div className="text-sm font-bold text-primary">${p.monthly_revenue} / mo</div>
                                    </div>
                                    <div className="w-full bg-surface-container-highest h-2 rounded-full overflow-hidden">
                                        <div 
                                            className="bg-primary h-full transition-all duration-700"
                                            style={{ width: `${(p.monthly_revenue / (totalRevenue || 1)) * 100}%` }}
                                        ></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* System Probes */}
                    <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
                        <h2 className="text-sm font-bold uppercase tracking-wider text-on-surface mb-6">Service Status</h2>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-3 bg-surface-container rounded-lg">
                                <div className="flex items-center gap-3">
                                    <span className="material-symbols-outlined text-primary">database</span>
                                    <span className="text-sm font-medium">Database (PostgreSQL)</span>
                                </div>
                                <span className="px-2 py-0.5 bg-secondary/10 text-secondary text-[10px] font-bold rounded">ONLINE</span>
                            </div>
                            <div className="flex items-center justify-between p-3 bg-surface-container rounded-lg">
                                <div className="flex items-center gap-3">
                                    <span className="material-symbols-outlined text-secondary">cached</span>
                                    <span className="text-sm font-medium">Redis Cache</span>
                                </div>
                                <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${system?.health.redis === 'connected' ? 'bg-secondary/10 text-secondary' : 'bg-tertiary/10 text-tertiary'}`}>
                                    {system?.health.redis.toUpperCase()}
                                </span>
                            </div>
                            <div className="flex items-center justify-between p-3 bg-surface-container rounded-lg">
                                <div className="flex items-center gap-3">
                                    <span className="material-symbols-outlined text-tertiary">api</span>
                                    <span className="text-sm font-medium">MetaApi Service</span>
                                </div>
                                <span className="px-2 py-0.5 bg-secondary/10 text-secondary text-[10px] font-bold rounded">OK</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
