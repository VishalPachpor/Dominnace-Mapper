"use client";
import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function PerformanceChart({ data }: { data: any[] }) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return <div className="h-[300px] w-full bg-slate-800 animate-pulse rounded-2xl"></div>;

    return (
        <div className="w-full h-[300px] bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-sm">
            <h3 className="text-white font-bold mb-4 tracking-tight">Equity Curve</h3>
            <ResponsiveContainer width="100%" height="90%">
                <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <XAxis dataKey="time" stroke="#64748b" tick={{ fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis stroke="#64748b" tick={{ fill: '#64748b' }} axisLine={false} tickLine={false} tickFormatter={(val) => `$${val}`} />
                    <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px" }}
                        itemStyle={{ color: "#22c55e", fontWeight: "bold" }}
                    />
                    <Line type="stepAfter" dataKey="pnl" stroke="#22c55e" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: "#22c55e", stroke: "#0f172a", strokeWidth: 2 }} />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
