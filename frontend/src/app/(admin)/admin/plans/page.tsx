"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

interface PlanDetail {
    id: string;
    name: string;
    price: number;
    users: number;
    monthly_revenue: number;
    max_strategies: number;
}

export default function AdminPlans() {
    const [plans, setPlans] = useState<PlanDetail[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchPlans = useCallback(async () => {
        try {
            const res = await api.get("/admin/plans");
            setPlans(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error("Failed to fetch plans", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPlans();
    }, [fetchPlans]);

    const totalMRR = plans.reduce((acc, p) => acc + p.monthly_revenue, 0);
    const totalSubscribers = plans.reduce((acc, p) => acc + p.users, 0);

    return (
        <div className="flex flex-col gap-6">
            <header>
                <h1 className="text-2xl font-bold text-on-surface">Subscription Plans</h1>
                <p className="text-sm text-on-surface-variant">Revenue and user distribution by tier.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-primary/5 border border-primary/10 p-6 rounded-xl flex items-center gap-6">
                    <div className="p-4 bg-primary rounded-2xl">
                        <span className="material-symbols-outlined text-on-primary text-4xl">payments</span>
                    </div>
                    <div>
                        <div className="text-[10px] text-primary uppercase font-bold tracking-widest leading-none mb-1">Total Estimated MRR</div>
                        <div className="text-3xl font-bold text-on-surface">${totalMRR.toLocaleString()}</div>
                    </div>
                </div>
                <div className="bg-secondary/5 border border-secondary/10 p-6 rounded-xl flex items-center gap-6">
                    <div className="p-4 bg-secondary rounded-2xl">
                        <span className="material-symbols-outlined text-on-secondary text-4xl">group</span>
                    </div>
                    <div>
                        <div className="text-[10px] text-secondary uppercase font-bold tracking-widest leading-none mb-1">Total Subscribers</div>
                        <div className="text-3xl font-bold text-on-surface">{totalSubscribers.toLocaleString()}</div>
                    </div>
                </div>
            </div>

            <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
                <table className="w-full text-left">
                    <thead>
                        <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/5">
                            <th className="py-4 px-6 font-medium">Plan Name</th>
                            <th className="py-4 px-6 font-medium">Pricing</th>
                            <th className="py-4 px-6 font-medium">Constraints</th>
                            <th className="py-4 px-6 font-medium">Subscribers</th>
                            <th className="py-4 px-6 font-medium text-right">Revenue Share</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-outline-variant/5">
                        {loading ? (
                            <tr>
                                <td colSpan={5} className="py-12 text-center text-sm text-on-surface-variant">Loading plan data...</td>
                            </tr>
                        ) : plans.map((p) => (
                            <tr key={p.id} className="hover:bg-surface-container-high/30 transition-colors">
                                <td className="py-4 px-6">
                                    <span className="text-sm font-bold text-on-surface">{p.name}</span>
                                </td>
                                <td className="py-4 px-6">
                                    <span className="text-sm text-on-surface">${p.price}/mo</span>
                                </td>
                                <td className="py-4 px-6">
                                    <span className="text-xs text-on-surface-variant">{p.max_strategies} max strategies</span>
                                </td>
                                <td className="py-4 px-6">
                                    <span className="px-2 py-0.5 bg-surface-container-high rounded text-xs font-bold text-on-surface">
                                        {p.users} users
                                    </span>
                                </td>
                                <td className="py-4 px-6 text-right">
                                    <div className="flex flex-col items-end">
                                        <span className="text-sm font-bold text-primary">${p.monthly_revenue.toLocaleString()}</span>
                                        <div className="w-24 bg-surface-container-highest h-1 mt-1 rounded-full overflow-hidden">
                                            <div 
                                                className="bg-primary h-full" 
                                                style={{ width: `${(p.monthly_revenue / (totalMRR || 1)) * 100}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
