"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";

interface Bot {
    id: string;
    name: string;
    slug: string;
    description: string;
    max_lot_size: number;
    is_active: boolean;
}

interface UserBot {
    id: string;
    bot_id: string;
    is_enabled: boolean;
}

export default function StrategyConfigPage() {
    const [bots, setBots] = useState<Bot[]>([]);
    const [userBots, setUserBots] = useState<UserBot[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Mock User limit for display
    const MAX_BOTS = 2; // Assuming Starter plan for demo

    useEffect(() => {
        const fetchBotsData = async () => {
            try {
                const [botsRes, userBotsRes] = await Promise.all([
                    api.get("/bots"),
                    api.get("/bots/my-subscriptions")
                ]);
                setBots(botsRes.data);
                setUserBots(userBotsRes.data);
            } catch (err) {
                console.error("Failed to load bots", err);
            } finally {
                setLoading(false);
            }
        };
        fetchBotsData();
    }, []);

    const activeCount = userBots.filter(ub => ub.is_enabled).length;

    const toggleBot = async (botId: string, currentStatus: boolean) => {
        setError(null);
        try {
            const res = await api.post(`/bots/${botId}/toggle`, {
                enabled: !currentStatus
            });
            
            // Update local state
            setUserBots(prev => {
                const existing = prev.find(ub => ub.bot_id === botId);
                if (existing) {
                    return prev.map(ub => ub.bot_id === botId ? { ...ub, is_enabled: !currentStatus } : ub);
                } else {
                    return [...prev, { id: res.data.id, bot_id: botId, is_enabled: !currentStatus }];
                }
            });
        } catch (err: any) {
            const msg = err.response?.data?.detail || "Failed to toggle bot.";
            setError(msg);
        }
    };

    if (loading) return <div className="p-8 text-on-surface">Loading strategies...</div>;

    return (
        <div className="flex flex-col gap-8 pb-12">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-headline font-bold text-on-surface tracking-tight">Strategy Configuration</h1>
                    <p className="text-on-surface-variant text-sm mt-1">Manage algorithmic subscriptions and portfolio allocation.</p>
                </div>
                
                <div className="bg-surface-container-low px-4 py-2 rounded-lg border border-outline-variant/10 flex items-center gap-4">
                    <div>
                        <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-widest">Plan: Starter</p>
                        <p className="text-sm font-medium text-on-surface mt-0.5">
                            {activeCount} / {MAX_BOTS} Active Strategies
                        </p>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-error-container text-on-error-container p-4 rounded-lg flex items-start gap-3 border border-error/20">
                    <span className="material-symbols-outlined text-error">warning</span>
                    <div>
                        <p className="text-sm font-bold text-error">Subscription Action Failed</p>
                        <p className="text-xs mt-0.5 opacity-90">{error}</p>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {bots.map(bot => {
                    const userSubscription = userBots.find(ub => ub.bot_id === bot.id);
                    const isActive = userSubscription?.is_enabled ?? false;

                    return (
                        <div key={bot.id} className={`bg-surface-container-low border ${isActive ? 'border-primary' : 'border-outline-variant/10'} rounded-xl overflow-hidden flex flex-col transition-all hover:border-primary/50`}>
                            <div className="p-6 flex-1">
                                <div className="flex justify-between items-start mb-4">
                                    <div className="w-12 h-12 bg-surface-container-highest rounded-lg flex items-center justify-center text-primary border border-outline-variant/5">
                                        <span className="material-symbols-outlined">smart_toy</span>
                                    </div>
                                    <div className="px-2.5 py-1 rounded bg-surface-container-highest text-[10px] font-bold tracking-widest text-on-surface-variant uppercase">
                                        Max Lot: {bot.max_lot_size}
                                    </div>
                                </div>
                                <h3 className="text-xl font-headline font-bold text-on-surface mb-2">{bot.name}</h3>
                                <p className="text-sm text-on-surface-variant leading-relaxed">
                                    {bot.description || "Quantitative momentum and mean-reversion strategy tuned for institutional execution metrics."}
                                </p>
                            </div>
                            
                            <div className="p-6 bg-surface-container-lowest border-t border-outline-variant/5 mt-auto flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-primary' : 'bg-on-surface-variant/40'}`}></div>
                                    <span className={`text-xs font-bold uppercase tracking-wider ${isActive ? 'text-primary' : 'text-on-surface-variant'}`}>
                                        {isActive ? "Active" : "Inactive"}
                                    </span>
                                </div>
                                
                                <button 
                                    onClick={() => toggleBot(bot.id, isActive)}
                                    // Disable enabling if we are at our limit, BUT allow disabling
                                    disabled={!isActive && activeCount >= MAX_BOTS}
                                    className={`px-4 py-2 rounded text-xs font-bold uppercase tracking-widest transition-colors ${
                                        isActive 
                                            ? "bg-surface-container hover:bg-surface-container-highest text-on-surface-variant hover:text-error" 
                                            : (!isActive && activeCount >= MAX_BOTS)
                                                ? "bg-surface-container-highest/50 text-on-surface-variant/30 cursor-not-allowed"
                                                : "bg-primary text-on-primary hover:bg-primary/90 shadow-lg shadow-primary/20"
                                    }`}
                                >
                                    {isActive ? "Disable" : "Enable"}
                                </button>
                            </div>
                        </div>
                    );
                })}

                {bots.length === 0 && (
                     <div className="col-span-full py-16 text-center border-2 border-dashed border-outline-variant/20 rounded-xl bg-surface-container-low/50">
                        <span className="material-symbols-outlined text-4xl text-on-surface-variant opacity-50 mb-3">extension_off</span>
                        <h3 className="text-lg font-bold text-on-surface">No Strategies Available</h3>
                        <p className="text-sm text-on-surface-variant max-w-md mx-auto mt-2">
                            The platform administrator has not published any algorithmic strategies yet. Please check back later.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
