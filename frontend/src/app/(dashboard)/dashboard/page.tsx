"use client";

import StatCard from "@/components/StatCard";
import PerformanceChart from "@/components/PerformanceChart";
import { useState, useEffect } from "react";
import api from "@/services/api";

export default function Dashboard() {
    const [botRunning, setBotRunning] = useState(true);
    const [stats, setStats] = useState({
        account_balance: 0,
        active_trades: 0,
        win_rate: 0,
        total_pnl: 0,
        equity_curve: []
    });

    useEffect(() => {
        api.get("/trades/dashboard")
            .then(res => setStats(res.data))
            .catch(err => console.error("Failed to load dashboard stats", err));
    }, []);

    const chartData = stats.equity_curve.length ? stats.equity_curve : [
        { time: "Today", pnl: 10000 }
    ];

    return (
        <div className="flex flex-col gap-6 max-w-7xl mx-auto">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold text-white tracking-tight">Trading Dashboard</h1>
                    <p className="text-slate-400 mt-1">Overview of your real-time performance and active bots.</p>
                </div>

                <div className="bg-slate-800 border border-slate-700 p-4 rounded-2xl flex items-center gap-6 shadow-sm">
                    <div>
                        <p className="text-sm text-slate-400 font-medium">Dominance Mapper Strategy</p>
                        <p className={`font-bold ${botRunning ? 'text-green-500' : 'text-red-500'}`}>
                            Status: {botRunning ? 'RUNNING' : 'STOPPED'}
                        </p>
                    </div>
                    <button
                        onClick={() => setBotRunning(!botRunning)}
                        className={`px-6 py-2 rounded-xl font-bold transition-colors shadow-lg ${botRunning ? 'bg-red-500/10 text-red-500 hover:bg-red-500/20 shadow-red-500/10' : 'bg-green-500 hover:bg-green-600 text-white shadow-green-500/20'}`}
                    >
                        {botRunning ? 'Stop Bot' : 'Start Bot'}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <StatCard title="Account Balance" value={`$${stats.account_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                <StatCard title="Active Trades" value={stats.active_trades.toString()} />
                <StatCard title="Win Rate" value={`${stats.win_rate}%`} positive={stats.win_rate >= 50} />
                <StatCard title="Total PnL" value={`${stats.total_pnl >= 0 ? '+' : '-'}$${Math.abs(stats.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} positive={stats.total_pnl >= 0} />
            </div>

            <div className="w-full">
                <PerformanceChart data={chartData} />
            </div>
        </div>
    );
}
