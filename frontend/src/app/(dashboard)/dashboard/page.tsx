"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";
import Link from "next/link";
import PerformanceChart from "@/components/PerformanceChart";

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

interface MtConnectionState {
    mt_status: string;
    can_trade?: boolean;
    meta_account_id?: string | null;
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
    const [mtState, setMtState] = useState<MtConnectionState>({
        mt_status: "disconnected",
        can_trade: true,
        meta_account_id: null,
    });
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [dashRes, posRes, mtRes] = await Promise.allSettled([
                api.get("/trades/dashboard", { params: { _ts: Date.now() } }),
                api.get("/positions", { params: { _ts: Date.now() } }),
                api.get("/users/mt-status", { params: { _ts: Date.now() } }),
            ]);

            if (dashRes.status === "fulfilled") setStats(dashRes.value.data);
            if (posRes.status === "fulfilled") {
                const posData = posRes.value.data;
                setPositions(Array.isArray(posData) ? posData : []);
            }
            if (mtRes.status === "fulfilled") {
                setMtState(mtRes.value.data || { mt_status: "disconnected" });
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

    useEffect(() => {
        const onAccountStatusChanged = () => {
            setLoading(true);
            fetchData();
        };
        window.addEventListener("dm:account-status-changed", onAccountStatusChanged);
        return () => window.removeEventListener("dm:account-status-changed", onAccountStatusChanged);
    }, [fetchData]);

    const fmt = (n: number) =>
        n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const hasLinkedMtAccount = Boolean(mtState.meta_account_id);
    const isInactiveAccount = mtState.can_trade === false && hasLinkedMtAccount;
    const visiblePositions = isInactiveAccount ? [] : positions;

    return (
        <div className="flex flex-col gap-6">
            {isInactiveAccount && (
                <div className="p-4 rounded-xl border border-tertiary/30 bg-tertiary-container/10">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-tertiary">warning</span>
                        <div>
                            <p className="text-sm font-bold text-tertiary">Account Inactive</p>
                            <p className="text-xs text-on-surface-variant mt-1">
                                Trading is paused because your linked account is inactive or expired. Metrics shown below are historical from your last active session.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* ─── 5-Column Stat Grid ─── */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {/* Total Balance */}
                <div className={`bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 ${isInactiveAccount ? "border-outline-variant/30 opacity-80" : "border-primary/10"}`}>
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        {isInactiveAccount ? "Last Known Balance" : "Total Balance"}
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
                <div className={`bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 ${isInactiveAccount ? "border-outline-variant/30 opacity-80" : "border-secondary/10"}`}>
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        {isInactiveAccount ? "Historical PnL" : "Daily PnL"}
                    </span>
                    <div className="mt-2 flex items-center gap-2">
                        <span className={`text-xl font-bold ${stats.total_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                            {stats.total_pnl >= 0 ? "+" : ""}${fmt(Math.abs(stats.total_pnl))}
                        </span>
                    </div>
                </div>

                {/* Open Profit */}
                <div className={`bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 ${isInactiveAccount ? "border-outline-variant/30 opacity-80" : "border-tertiary/10"}`}>
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        {isInactiveAccount ? "Live Open PnL (Paused)" : "Open Profit"}
                    </span>
                    <div className="mt-2 flex items-center gap-2">
                        {isInactiveAccount ? (
                            <span className="text-xl font-bold text-on-surface-variant">--</span>
                        ) : (
                            <>
                                <span className={`text-xl font-bold ${stats.unrealized_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                                    {stats.unrealized_pnl >= 0 ? "+" : ""}${fmt(Math.abs(stats.unrealized_pnl))}
                                </span>
                                <span className={`material-symbols-outlined text-sm ${stats.unrealized_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                                    {stats.unrealized_pnl >= 0 ? "trending_up" : "trending_down"}
                                </span>
                            </>
                        )}
                    </div>
                </div>

                {/* Win Rate */}
                <div className={`bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 ${isInactiveAccount ? "border-outline-variant/30 opacity-80" : "border-primary/10"}`}>
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
                <div className={`bg-surface-container p-4 rounded-lg flex flex-col justify-between border-b-2 ${isInactiveAccount ? "border-outline-variant/30 opacity-80" : "border-secondary/10"}`}>
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                        Active Trades
                    </span>
                    <div className="mt-2 flex items-center gap-2">
                        <span className="text-xl font-bold text-on-surface">
                            {isInactiveAccount ? 0 : stats.active_trades}
                        </span>
                        {!isInactiveAccount && (
                            <span className="material-symbols-outlined text-secondary text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
                                speed
                            </span>
                        )}
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
                                {isInactiveAccount
                                    ? `Historical equity curve (inactive account) (${stats.equity_curve.length} points)`
                                    : `Cumulative Equity Growth (${stats.equity_curve.length} points)`}
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
                    <div className="flex-1 min-h-[300px] md:min-h-[400px] px-6 pb-6">
                        <PerformanceChart
                            data={stats.equity_curve}
                            height={400}
                            showReferenceLine={true}
                            loading={loading}
                        />
                    </div>
                </div>

                {/* Active Trades Panel — Now Live */}
                <div className="lg:col-span-4 bg-surface-container-low rounded-xl flex flex-col overflow-hidden">
                    <div className="p-6 border-b border-outline-variant/10 flex items-center justify-between">
                            <h2 className="text-sm font-bold uppercase tracking-wider text-on-surface">Active Trades</h2>
                            <span className="px-2 py-0.5 bg-surface-container-high rounded text-[10px] font-mono text-on-surface-variant">
                                {visiblePositions.length} TOTAL
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
                                {visiblePositions.length === 0 ? (
                                    <tr>
                                        <td colSpan={3} className="py-12 text-center text-sm text-on-surface-variant">
                                            {isInactiveAccount ? "Account inactive. Live positions are paused." : "No active trades right now."}
                                        </td>
                                    </tr>
                                ) : (
                                    visiblePositions.map((p, i) => (
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
                        {isInactiveAccount
                            ? "Trading is paused while this account is inactive. Connect or replace the MT5 account to resume live execution."
                            : stats.active_trades > 0
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
                        Win rate: {stats.win_rate}%. Total closed PnL: {stats.total_pnl >= 0 ? "+" : ""}${fmt(Math.abs(stats.total_pnl))}.{" "}
                        {isInactiveAccount ? "Last known balance" : "Balance"}: ${fmt(stats.account_balance)}.
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
