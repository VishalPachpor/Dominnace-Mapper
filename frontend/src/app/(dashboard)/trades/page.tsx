"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";

export default function Trades() {
    const [trades, setTrades] = useState<any[]>([]);

    useEffect(() => {
        // Expected endpoint: GET /trades from backend
        api.get("/trades")
            .then(res => setTrades(res.data))
            .catch(err => console.error("Error fetching trades", err));
    }, []);

    return (
        <div className="max-w-7xl mx-auto flex flex-col gap-6 text-white">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Trade History</h1>
                    <p className="text-slate-400 mt-1">Review all closed trades, win rate history, and past performances.</p>
                </div>
            </div>

            <div className="bg-slate-800 rounded-2xl overflow-hidden border border-slate-700 shadow-sm">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-900/50 text-slate-400">
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Symbol</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Side</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Entry</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Exit</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">PnL</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Result</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trades.length > 0 ? trades.map((trade, idx) => (
                            <tr key={idx} className="hover:bg-slate-800/80 transition-colors group">
                                <td className="p-4 border-b border-slate-700 font-bold text-white">{trade.symbol}</td>
                                <td className={`p-4 border-b border-slate-700 font-bold ${trade.side === 'buy' ? 'text-green-500' : 'text-red-500'}`}>{trade.side.toUpperCase()}</td>
                                <td className="p-4 border-b border-slate-700 text-slate-200">{trade.entry}</td>
                                <td className="p-4 border-b border-slate-700 text-slate-200">{trade.exit}</td>
                                <td className={`p-4 border-b border-slate-700 font-bold ${trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>${trade.pnl}</td>
                                <td className="p-4 border-b border-slate-700">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${trade.result === 'WIN' ? 'bg-green-500/20 text-green-400' : trade.result === 'LOSS' ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-400'}`}>
                                        {trade.result}
                                    </span>
                                </td>
                            </tr>
                        )) : (
                            <tr>
                                <td colSpan={6} className="p-6 text-center text-gray-500">No trade history recorded yet.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
