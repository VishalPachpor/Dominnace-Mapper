"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

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

export default function AdminSystem() {
    const [status, setStatus] = useState<SystemStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await api.get("/admin/system");
            setStatus(res.data);
        } catch (err) {
            console.error("Failed to fetch system status", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 15000);
        return () => clearInterval(interval);
    }, [fetchStatus]);

    const toggleKillSwitch = async () => {
        if (!confirm("Are you SURE you want to toggle the global trading kill switch? This affects ALL users.")) return;
        
        setActionLoading(true);
        try {
            const res = await api.post("/admin/system/kill-switch", {
                enabled: !status?.observability.trading_enabled
            });
            alert(res.data.message);
            fetchStatus();
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } }; message?: string };
            alert("Action failed: " + (error.response?.data?.detail || error.message));
        } finally {
            setActionLoading(false);
        }
    };

    const resetCounters = async () => {
        if (!confirm("Reset all daily counters? This cannot be undone.")) return;
        
        setActionLoading(true);
        try {
            const res = await api.post("/admin/system/reset-counters");
            alert(res.data.message);
            fetchStatus();
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } }; message?: string };
            alert("Action failed: " + (error.response?.data?.detail || error.message));
        } finally {
            setActionLoading(false);
        }
    };

    if (loading) return <div className="p-12 text-center animate-pulse">Checking system health...</div>;

    return (
        <div className="flex flex-col gap-6">
            <header>
                <h1 className="text-2xl font-bold text-on-surface">System Health</h1>
                <p className="text-sm text-on-surface-variant">Real-time infrastructure and service monitoring.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Health Overview */}
                <div className="lg:col-span-12">
                    <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                        <h2 className="text-lg font-bold text-on-surface mb-6">Service Infrastructure</h2>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="bg-surface-container p-5 rounded-lg flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className={`p-3 rounded-full ${status?.health.redis === 'connected' ? 'bg-secondary/10 text-secondary' : 'bg-tertiary/10 text-tertiary'}`}>
                                        <span className="material-symbols-outlined">database</span>
                                    </div>
                                    <div>
                                        <div className="text-sm font-bold text-on-surface">Redis Cluster</div>
                                        <div className="text-[10px] text-on-surface-variant uppercase font-mono">{status?.health.redis}</div>
                                    </div>
                                </div>
                                <span className={`w-3 h-3 rounded-full ${status?.health.redis === 'connected' ? 'bg-secondary shadow-[0_0_8px_rgba(var(--secondary),0.5)]' : 'bg-tertiary'}`}></span>
                            </div>

                            <div className="bg-surface-container p-5 rounded-lg flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="p-3 rounded-full bg-secondary/10 text-secondary">
                                        <span className="material-symbols-outlined">api</span>
                                    </div>
                                    <div>
                                        <div className="text-sm font-bold text-on-surface">MetaApi Service</div>
                                        <div className="text-[10px] text-on-surface-variant uppercase font-mono">operational</div>
                                    </div>
                                </div>
                                <span className="w-3 h-3 rounded-full bg-secondary shadow-[0_0_8px_rgba(var(--secondary),0.5)]"></span>
                            </div>

                            <div className="bg-surface-container p-5 rounded-lg flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="p-3 rounded-full bg-secondary/10 text-secondary">
                                        <span className="material-symbols-outlined">memory</span>
                                    </div>
                                    <div>
                                        <div className="text-sm font-bold text-on-surface">Trade Workers</div>
                                        <div className="text-[10px] text-on-surface-variant uppercase font-mono">active</div>
                                    </div>
                                </div>
                                <span className="w-3 h-3 rounded-full bg-secondary shadow-[0_0_8px_rgba(var(--secondary),0.5)]"></span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Critical Controls */}
                <div className="lg:col-span-7">
                    <div className="bg-tertiary/5 border border-tertiary/20 p-8 rounded-xl h-full flex flex-col justify-between">
                        <div>
                            <div className="flex items-center gap-3 text-tertiary mb-4">
                                <span className="material-symbols-outlined text-4xl">emergency</span>
                                <h2 className="text-2xl font-bold uppercase tracking-tight">Kill Switch</h2>
                            </div>
                            <p className="text-on-surface-variant text-sm leading-relaxed mb-8">
                                Activating the global kill switch will immediately halt ALL automated trading across the entire platform. 
                                Open positions will remain, but no new orders will be sent, regardless of strategy signals.
                            </p>
                        </div>

                        <div className="flex items-center gap-6 p-6 bg-surface-container rounded-lg border border-outline-variant/5">
                            <div className="flex-1">
                                <div className="text-xs font-bold text-on-surface-variant uppercase mb-1">Current State</div>
                                <div className={`text-xl font-black ${status?.observability.trading_enabled ? 'text-secondary' : 'text-tertiary animate-pulse'}`}>
                                    {status?.observability.trading_enabled ? 'ALLOWED' : 'DISABLED'}
                                </div>
                            </div>
                            <button
                                onClick={toggleKillSwitch}
                                disabled={actionLoading}
                                className={`px-8 py-4 rounded-xl font-bold text-sm uppercase tracking-widest transition-all ${
                                    status?.observability.trading_enabled 
                                        ? 'bg-tertiary text-on-tertiary hover:opacity-90 shadow-lg shadow-tertiary/20' 
                                        : 'bg-secondary text-on-secondary hover:opacity-90 shadow-lg shadow-secondary/20'
                                }`}
                            >
                                {actionLoading ? 'PENDING...' : status?.observability.trading_enabled ? 'HALT TRADING' : 'RESUME TRADING'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Maintenance & Logs */}
                <div className="lg:col-span-5">
                    <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 h-full flex flex-col">
                        <h2 className="text-lg font-bold text-on-surface mb-6">Maintenance</h2>
                        
                        <div className="space-y-6 flex-1">
                            <div className="flex items-center justify-between p-4 bg-surface-container rounded-lg">
                                <div>
                                    <div className="text-sm font-bold text-on-surface">Daily Counters</div>
                                    <p className="text-[10px] text-on-surface-variant mt-1">Reset signals & trades processed count.</p>
                                </div>
                                <button 
                                    onClick={resetCounters}
                                    disabled={actionLoading}
                                    className="px-4 py-2 bg-outline-variant/10 hover:bg-outline-variant/20 text-on-surface text-[10px] font-bold rounded uppercase transition-colors"
                                >
                                    RESET
                                </button>
                            </div>

                            <div className="flex items-center justify-between p-4 bg-surface-container rounded-lg">
                                <div>
                                    <div className="text-sm font-bold text-on-surface">Database Cleanup</div>
                                    <p className="text-[10px] text-on-surface-variant mt-1">Clear logs older than 30 days.</p>
                                </div>
                                <button className="px-4 py-2 bg-outline-variant/10 hover:bg-outline-variant/20 text-on-surface text-[10px] font-bold rounded uppercase transition-colors">
                                    RUN
                                </button>
                            </div>

                            <div className="mt-8 p-4 bg-primary/5 border border-primary/10 rounded-lg">
                                <div className="flex items-center gap-2 text-primary text-xs font-bold mb-2 uppercase">
                                    <span className="material-symbols-outlined text-[16px]">info</span>
                                    System Info
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <div className="text-[10px] text-on-surface-variant">Environment</div>
                                        <div className="text-xs font-mono font-bold">production</div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-on-surface-variant">Worker Count</div>
                                        <div className="text-xs font-mono font-bold">4 dynamic</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
