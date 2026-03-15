"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import api from "@/services/api";

interface LeaderboardBot {
    bot_id: string;
    name: string;
    slug: string;
    symbol: string;
    win_rate: number;
    total_pnl: number;
    total_trades: number;
}

export default function PublicLeaderboardPage() {
    const [bots, setBots] = useState<LeaderboardBot[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchLeaderboard = async () => {
            try {
                const res = await api.get("/bots/public/leaderboard");
                setBots(res.data);
            } catch (err) {
                console.error("Failed to fetch leaderboard", err);
            } finally {
                setLoading(false);
            }
        };
        fetchLeaderboard();
    }, []);

    return (
        <div className="min-h-screen bg-surface text-on-surface font-sans selection:bg-primary/20">
            {/* Header / Nav */}
            <header className="px-8 py-6 flex items-center justify-between border-b border-outline-variant/10 bg-surface-container-lowest sticky top-0 z-50">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-primary flex items-center justify-center text-on-primary font-bold">
                        D
                    </div>
                    <span className="font-headline font-bold text-xl tracking-tight">Dominance</span>
                </div>
                <div className="flex items-center gap-4">
                    <Link href="/login" className="text-sm font-medium text-on-surface-variant hover:text-on-surface transition-colors">
                        Sign In
                    </Link>
                    <Link href="/register" className="px-5 py-2.5 bg-primary text-on-primary text-sm font-bold rounded hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20">
                        Start Free Trial
                    </Link>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative pt-24 pb-16 px-6 overflow-hidden flex flex-col items-center text-center">
                {/* Background Grid & Glow */}
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay"></div>
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-primary/20 blur-[120px] rounded-full pointer-events-none"></div>

                <div className="relative z-10 max-w-3xl">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold tracking-widest uppercase mb-6">
                        <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                        Live Marketplace Now Open
                    </div>
                    <h1 className="text-5xl md:text-6xl font-headline font-bold mb-6 tracking-tight leading-tight">
                        Institutional Grade <br/>
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-tertiary">
                            Algorithmic Strategies
                        </span>
                    </h1>
                    <p className="text-lg text-on-surface-variant mb-10 max-w-2xl mx-auto leading-relaxed">
                        Connect your broker and automatically copy our highest-performing quantitative models. Transparent performance. Zero hidden fees.
                    </p>
                    
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href="/register" className="px-8 py-4 bg-primary text-on-primary rounded font-bold text-lg hover:bg-primary/90 transition-all shadow-xl shadow-primary/20 hover:scale-105 active:scale-95 w-full sm:w-auto">
                            Connect Exchange
                        </Link>
                        <a href="#performance" className="px-8 py-4 bg-surface-container-high text-on-surface rounded font-bold border border-outline-variant/10 hover:bg-surface-container-highest transition-all w-full sm:w-auto">
                            View Performance Data
                        </a>
                    </div>
                </div>
            </section>

            {/* Leaderboard Section */}
            <section id="performance" className="py-20 px-6 bg-surface-container-lowest border-t border-outline-variant/5">
                <div className="max-w-6xl mx-auto">
                    <div className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
                        <div>
                            <h2 className="text-3xl font-headline font-bold tracking-tight mb-2">Strategy Leaderboard</h2>
                            <p className="text-on-surface-variant">Live forward-tested performance across all users.</p>
                        </div>
                        <div className="flex items-center gap-2 text-xs font-bold tracking-widest uppercase text-on-surface-variant bg-surface-container-low px-4 py-2 rounded border border-outline-variant/10">
                            <span className="material-symbols-outlined text-[16px]">update</span>
                            Live Results
                        </div>
                    </div>

                    {loading ? (
                        <div className="py-20 flex justify-center items-center">
                            <div className="w-8 h-8 rounded-full border-4 border-primary/30 border-t-primary animate-spin"></div>
                        </div>
                    ) : (
                        <div className="bg-surface-container-low border border-outline-variant/10 rounded-xl overflow-hidden shadow-2xl">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="bg-surface-container-lowest border-b border-outline-variant/10 text-[10px] uppercase font-bold tracking-widest text-on-surface-variant">
                                            <th className="p-4 pl-6">Strategy Engine</th>
                                            <th className="p-4">Symbol</th>
                                            <th className="p-4">Total Trades</th>
                                            <th className="p-4">Win Rate</th>
                                            <th className="p-4 pr-6 text-right">Net Profit (30D)</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-outline-variant/5">
                                        {bots.map((bot, idx) => (
                                            <tr key={bot.bot_id} className="hover:bg-surface-container-high/50 transition-colors group">
                                                <td className="p-4 pl-6">
                                                    <div className="flex items-center gap-4">
                                                        <div className="w-10 h-10 rounded bg-surface-container-highest flex items-center justify-center text-on-surface border border-outline-variant/10 group-hover:border-primary/50 transition-colors">
                                                            {idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : "⚡"}
                                                        </div>
                                                        <div>
                                                            <div className="font-bold text-on-surface">{bot.name}</div>
                                                            <div className="text-xs text-on-surface-variant">{bot.slug}</div>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="p-4">
                                                    <div className="inline-flex items-center px-2.5 py-1 rounded bg-surface-container font-medium text-xs border border-outline-variant/5">
                                                        {bot.symbol}
                                                    </div>
                                                </td>
                                                <td className="p-4 font-mono text-sm text-on-surface-variant font-medium">
                                                    {bot.total_trades}
                                                </td>
                                                <td className="p-4">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-16 h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                                                            <div 
                                                                className={`h-full ${bot.win_rate >= 50 ? 'bg-primary' : 'bg-warning'}`}
                                                                style={{ width: `${bot.win_rate}%` }}
                                                            ></div>
                                                        </div>
                                                        <span className="font-mono text-sm font-bold text-on-surface">{bot.win_rate}%</span>
                                                    </div>
                                                </td>
                                                <td className="p-4 pr-6 text-right">
                                                    <div className={`font-mono text-lg tracking-tight font-bold ${
                                                        bot.total_pnl > 0 ? 'text-primary' : (bot.total_pnl < 0 ? 'text-error' : 'text-on-surface-variant')
                                                    }`}>
                                                        {bot.total_pnl > 0 ? '+' : ''}{bot.total_pnl} USD
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}

                                        {bots.length === 0 && (
                                            <tr>
                                                <td colSpan={5} className="p-12 text-center">
                                                    <span className="material-symbols-outlined text-4xl text-on-surface-variant opacity-50 mb-2">monitoring</span>
                                                    <p className="text-on-surface-variant font-medium">No performance data available yet.</p>
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {/* Footer */}
            <footer className="py-12 px-6 border-t border-outline-variant/10 text-center text-on-surface-variant text-sm">
                <div className="max-w-4xl mx-auto flex flex-col items-center gap-4">
                    <div className="w-8 h-8 rounded bg-surface-container flex items-center justify-center text-on-surface font-bold opacity-50 grayscale">
                        D
                    </div>
                    <p>© 2026 DominanceBot Quantitative Systems. All rights reserved.</p>
                    <p className="text-xs opacity-70 max-w-2xl mx-auto">
                        Trading foreign exchange on margin carries a high level of risk, and may not be suitable for all investors. 
                        Past performance is not indicative of future results. The high degree of leverage can work against you as well as for you.
                    </p>
                </div>
            </footer>
        </div>
    );
}
