"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";

export default function Positions() {
    const [positions, setPositions] = useState<any[]>([]);

    useEffect(() => {
        // Expected endpoint: GET /positions from backend
        api.get("/positions")
            .then(res => setPositions(res.data))
            .catch(err => console.error("Error fetching positions", err));
    }, []);

    return (
        <div className="max-w-7xl mx-auto flex flex-col gap-6">
            <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Active Positions</h1>
                <p className="text-slate-400 mt-1">Real-time monitoring of open trades executing on the exchange.</p>
            </div>

            <div className="bg-slate-800 rounded-2xl overflow-hidden border border-slate-700 shadow-sm">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-900/50 text-slate-400">
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Symbol</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Side</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">Entry</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">SL</th>
                            <th className="p-4 font-semibold uppercase text-xs tracking-wider border-b border-slate-700">TP</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions.length > 0 ? positions.map((pos, idx) => (
                            <tr key={idx} className="hover:bg-slate-800/80 transition-colors group">
                                <td className="p-4 border-b border-slate-700 font-bold text-white">{pos.symbol}</td>
                                <td className={`p-4 border-b border-slate-700 font-bold ${pos.side === 'buy' ? 'text-green-500' : 'text-red-500'}`}>{pos.side.toUpperCase()}</td>
                                <td className="p-4 border-b border-slate-700 text-slate-200">{pos.entry}</td>
                                <td className="p-4 border-b border-slate-700 text-red-400/80 group-hover:text-red-400 transition-colors">{pos.sl}</td>
                                <td className="p-4 border-b border-slate-700 text-green-400/80 group-hover:text-green-400 transition-colors">{pos.tp}</td>
                            </tr>
                        )) : (
                            <tr>
                                <td colSpan={5} className="p-6 text-center text-gray-500">No active positions right now.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
