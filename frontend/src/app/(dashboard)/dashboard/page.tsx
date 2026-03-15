"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";
import Link from "next/link";

interface DashboardStats {
    account_balance: number;
    active_trades: number;
    win_rate: number;
    total_pnl: number;
    unrealized_pnl: number;
    equity_curve: { time: string; pnl: number }[];
}

interface LivePosition {
    id: string;
    symbol: string;
    type: string;
    profit: number;
    volume: number;
}

export default function Dashboard() {
    const [stats, setStats] = useState<DashboardStats>({
        account_balance: 0,
        active_trades: 0,
        win_rate: 0,
        total_pnl: 0,
        unrealized_pnl: 0,
        equity_curve: [],
    });
    const [positions, setPositions] = useState<LivePosition[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [dashRes, posRes] = await Promise.allSettled([
                api.get("/trades/dashboard"),
                api.get("/trades/positions"),
            ]);

            if (dashRes.status === "fulfilled") setStats(dashRes.value.data);
            if (posRes.status === "fulfilled") {
                const posData = posRes.value.data;
                setPositions(Array.isArray(posData) ? posData : []);
            }
        } catch (err) {
            console.error("Dashboard fetch failed", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // refresh every 30s
        return () => clearInterval(interval);
    }, [fetchData]);

    const fmt = (n: number) =>
        n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    // ── Build dynamic SVG path from equity_curve data ──
    const buildChartPath = () => {
        const data = stats.equity_curve;
        if (!data || data.length === 0) return { line: "", area: "" };

        const W = 800, H = 300;
        const vals = data.map(d => d.pnl);
        const min = Math.min(...vals);
        const max = Math.max(...vals);
        const range = max - min || 1;

        const points = data.map((d, i) => {
            const x = data.length === 1 ? W / 2 : (i / (data.length - 1)) * W;
            const y = H - 30 - ((d.pnl - min) / range) * (H - 60);
            return { x, y };
        });

        if (points.length === 1) {
            const p = points[0];
            return {
                line: `M${p.x - 50},${p.y} L${p.x + 50},${p.y}`,
                area: `M${p.x - 50},${p.y} L${p.x + 50},${p.y} L${p.x + 50},${H} L${p.x - 50},${H} Z`,
            };
        }

        let path = `M${points[0].x},${points[0].y}`;
        for (let i = 1; i < points.length; i++) {
            const cp1x = (points[i - 1].x + points[i].x) / 2;
            const cp1y = points[i - 1].y;
            const cp2x = cp1x;
            const cp2y = points[i].y;
            path += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${points[i].x},${points[i].y}`;
        }

        const last = points[points.length - 1];
        const area = path + ` L${last.x},${H} L${points[0].x},${H} Z`;

        return { line: path, area, lastPoint: last };
    };

    const chart = buildChartPath();

    return (
        <div className="flex flex-col gap-6">
            {/* ─── 5-Column Stat Grid ─── */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {/* Total Balance */}
                <div className="bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 border-primary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        Total Balance
                    </span>
                    <div className="mt-2 flex items-baseline gap-1">
                        <span className="text-xl font-bold text-on-surface">
                            ${Math.floor(stats.account_balance).toLocaleString()}
                        </span>
                        <span className="text-[10px] font-mono text-on-surface-variant">
                            .{(stats.account_balance % 1).toFixed(2).slice(2)}
                        </span>
                    </div>
                </div>

                {/* Daily PnL */}
                <div className="bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 border-secondary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        Daily PnL
                    </span>
                    <div className="mt-2 flex items-center gap-2">
                        <span className={`text-xl font-bold ${stats.total_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {stats.total_pnl >= 0 ? "+" : ""}${fmt(Math.abs(stats.total_pnl))}
                        </span>
                    </div>
                </div>

                {/* Open Profit */}
                <div className="bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 border-tertiary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        Open Profit
                    </span>
                    <div className="mt-2 flex items-center gap-2">
                        <span className={`text-xl font-bold ${stats.unrealized_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {stats.unrealized_pnl >= 0 ? "+" : ""}${fmt(Math.abs(stats.unrealized_pnl))}
                        </span>
                        <span className={`material-symbols-outlined text-sm ${stats.unrealized_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {stats.unrealized_pnl >= 0 ? "trending_up" : "trending_down"}
                        </span>
                    </div>
                </div>

                {/* Win Rate */}
                <div className="bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 border-primary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        Win Rate %
                    </span>
                    <div className="mt-2">
                        <span className="text-xl font-bold text-on-surface">
                            {stats.win_rate}%
                        </span>
                        <div className="w-full bg-surface-container-highest h-1 mt-2 rounded-full overflow-hidden">
                            <div
                                className="bg-primary h-full transition-all duration-500"
                                style={{ width: `${Math.min(stats.win_rate, 100)}%` }}
                            ></div>
                        </div>
                    </div>
                </div>

                {/* Active Trades */}
                <div className="bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 border-secondary/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        Active Trades
                    </span>
                    <div className="mt-2 flex items-center gap-2">
                        <span className="text-xl font-bold text-on-surface">
                            {stats.active_trades}
                        </span>
                        <span className="material-symbols-outlined text-secondary text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
                            speed
                        </span>
                    </div>
                </div>
            </div>

            {/* ─── Performance Curve + Active Trades ─── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Equity Curve — Now Dynamic */}
                <div className="lg:col-span-8 bg-surface-container-low rounded-xl flex flex-col">
                    <div className="p-6 flex items-center justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-on-surface">Performance Curve</h2>
                            <p className="text-xs text-on-surface-variant">
                                Cumulative Equity Growth ({stats.equity_curve.length} points)
                            </p>
                        </div>
                        {stats.equity_curve.length > 0 && (
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-on-surface-variant font-mono">
                                    {stats.equity_curve[0].time}
                                </span>
                                <span className="text-[10px] text-on-surface-variant">→</span>
                                <span className="text-[10px] text-on-surface-variant font-mono">
                                    {stats.equity_curve[stats.equity_curve.length - 1].time}
                                </span>
                            </div>
                        )}
                    </div>
                    <div className="flex-1 min-h-[300px] md:min-h-[400px] relative px-6 pb-6">
                        <div className="w-full h-full relative">
                            {/* Grid lines */}
                            <div className="absolute inset-0 grid grid-cols-6 gap-x-px">
                                {[...Array(5)].map((_, i) => <div key={i} className="border-r border-outline-variant/10"></div>)}
                                <div></div>
                            </div>
                            <div className="absolute inset-0 grid grid-rows-5 gap-y-px">
                                {[...Array(4)].map((_, i) => <div key={i} className="border-b border-outline-variant/10"></div>)}
                                <div></div>
                            </div>
                            {/* Dynamic SVG from equity_curve data */}
                            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 800 300" preserveAspectRatio="none">
                                <defs>
                                    <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#2d60ff" stopOpacity="0.2" />
                                        <stop offset="100%" stopColor="#2d60ff" stopOpacity="0" />
                                    </linearGradient>
                                </defs>
                                {chart.area && <path d={chart.area} fill="url(#chartGradient)" />}
                                {chart.line && <path d={chart.line} fill="none" stroke="#b7c4ff" strokeLinecap="round" strokeWidth="2.5" />}
                                {chart.lastPoint && (
                                    <>
                                        <circle cx={chart.lastPoint.x} cy={chart.lastPoint.y} fill="#b7c4ff" r="4" />
                                        <circle cx={chart.lastPoint.x} cy={chart.lastPoint.y} fill="#b7c4ff" fillOpacity="0.15" r="12" />
                                    </>
                                )}
                            </svg>
                            {loading && !chart.line && (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className="text-sm text-on-surface-variant">Loading chart data…</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Active Trades Panel — Now Live */}
                <div className="lg:col-span-4 bg-surface-container-low rounded-xl flex flex-col overflow-hidden">
                    <div className="p-6 border-b border-outline-variant/10 flex items-center justify-between">
                        <h2 className="text-sm font-bold uppercase tracking-wider text-on-surface">Active Trades</h2>
                        <span className="px-2 py-0.5 bg-surface-container-high rounded text-[10px] font-mono text-on-surface-variant">
                            {positions.length} TOTAL
                        </span>
                    </div>
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest">
                                    <th className="py-3 px-6 font-medium">Pair</th>
                                    <th className="py-3 px-2 font-medium">Side</th>
                                    <th className="py-3 px-6 text-right font-medium">PnL</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-outline-variant/5">
                                {positions.length === 0 ? (
                                    <tr>
                                        <td colSpan={3} className="py-12 text-center text-sm text-on-surface-variant">
                                            No active trades right now.
                                        </td>
                                    </tr>
                                ) : (
                                    positions.map((p, i) => (
                                        <tr key={p.id || i} className="hover:bg-surface-container-high/50 transition-colors">
                                            <td className="py-3 px-6">
                                                <span className="text-sm font-bold text-on-surface">{p.symbol}</span>
                                            </td>
                                            <td className="py-3 px-2">
                                                <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-sm border ${
                                                    p.type?.toUpperCase().includes("BUY")
                                                        ? "bg-secondary-container/20 text-secondary border-secondary/20"
                                                        : "bg-tertiary-container/20 text-tertiary border-tertiary/20"
                                                }`}>
                                                    {p.type?.toUpperCase().includes("BUY") ? "LONG" : "SHORT"}
                                                </span>
                                            </td>
                                            <td className={`py-3 px-6 text-right text-sm font-mono font-bold ${
                                                (p.profit || 0) >= 0 ? "text-secondary" : "text-tertiary"
                                            }`}>
                                                {(p.profit || 0) >= 0 ? "+" : ""}${(p.profit || 0).toFixed(2)}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                    <div className="p-4 bg-surface-container-lowest/50 border-t border-outline-variant/10">
                        <Link href="/positions" className="w-full py-2.5 text-xs font-bold text-on-surface hover:text-primary transition-colors flex items-center justify-center gap-2">
                            View All Positions
                            <span className="material-symbols-outlined text-sm">arrow_forward</span>
                        </Link>
                    </div>
                </div>
            </div>

            {/* ─── Quick Info Row ─── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/5">
                    <div className="flex items-center justify-between mb-4">
                        <span className="material-symbols-outlined text-primary">security</span>
                        <span className={`text-[10px] font-bold uppercase tracking-widest ${
                            stats.total_pnl >= 0 ? "text-secondary" : "text-tertiary"
                        }`}>
                            {stats.total_pnl >= 0 ? "Safe" : "Caution"}
                        </span>
                    </div>
                    <h3 className="text-sm font-bold text-on-surface mb-1">Risk Monitor</h3>
                    <p className="text-xs text-on-surface-variant leading-relaxed">
                        {stats.active_trades > 0
                            ? `${stats.active_trades} active position(s). Unrealized PnL: ${stats.unrealized_pnl >= 0 ? "+" : ""}$${fmt(Math.abs(stats.unrealized_pnl))}.`
                            : "No active positions. Risk exposure is zero."}
                    </p>
                </div>
                <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/5">
                    <div className="flex items-center justify-between mb-4">
                        <span className="material-symbols-outlined text-primary">query_stats</span>
                        <span className="text-[10px] font-bold text-primary uppercase tracking-widest">Stats</span>
                    </div>
                    <h3 className="text-sm font-bold text-on-surface mb-1">Performance Summary</h3>
                    <p className="text-xs text-on-surface-variant leading-relaxed">
                        Win rate: {stats.win_rate}%. Total closed PnL: {stats.total_pnl >= 0 ? "+" : ""}${fmt(Math.abs(stats.total_pnl))}.
                        Balance: ${fmt(stats.account_balance)}.
                    </p>
                </div>
                <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/5">
                    <div className="flex items-center justify-between mb-4">
                        <span className="material-symbols-outlined text-secondary">hub</span>
                        <span className="text-[10px] font-bold text-secondary uppercase tracking-widest">Quick Links</span>
                    </div>
                    <h3 className="text-sm font-bold text-on-surface mb-3">Navigate</h3>
                    <div className="flex items-center gap-3">
                        <Link href="/positions" className="px-4 py-2 bg-surface-container-high rounded text-[10px] font-bold uppercase tracking-wider hover:bg-surface-container-highest transition-colors">
                            Positions
                        </Link>
                        <Link href="/trades" className="px-4 py-2 bg-surface-container-high rounded text-[10px] font-bold uppercase tracking-wider hover:bg-surface-container-highest transition-colors">
                            History
                        </Link>
                        <Link href="/settings" className="px-4 py-2 bg-primary-container text-on-primary-container rounded text-[10px] font-bold uppercase tracking-wider hover:opacity-90 transition-all">
                            Accounts
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
