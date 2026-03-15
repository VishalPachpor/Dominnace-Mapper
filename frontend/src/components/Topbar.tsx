"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import api from "@/services/api";

interface MtStatus {
    mt_status: string;
    mt_broker: string | null;
}

interface UserMini {
    full_name: string;
    email: string;
    avatar_url: string;
}

export default function Topbar({ toggleSidebar }: { toggleSidebar?: () => void }) {
    const [status, setStatus] = useState<MtStatus>({ mt_status: "disconnected", mt_broker: null });
    const [user, setUser] = useState<UserMini | null>(null);

    useEffect(() => {
        const fetchStatus = () => {
            api.get("/users/mt-status")
                .then(res => setStatus(res.data))
                .catch(() => {});
        };
        fetchStatus();
        const interval = setInterval(fetchStatus, 30000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        api.get("/users/me")
            .then(res => setUser(res.data))
            .catch(() => {});
    }, []);

    const isConnected = status.mt_status === "connected";
    const isConnecting = status.mt_status === "connecting" || status.mt_status === "deploying";

    return (
        <header className="h-16 flex items-center justify-between px-6 bg-surface border-b border-outline-variant/15 text-on-surface z-40 relative">
            <div className="flex items-center gap-6">
                {/* Mobile hamburger */}
                <button
                    onClick={toggleSidebar}
                    className="md:hidden p-2 -ml-2 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container-high focus:outline-none"
                    aria-label="Toggle Menu"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </button>

                <span className="text-sm font-semibold text-on-surface hidden md:block">DominanceBot</span>

                <div className="flex items-center gap-4">
                    {/* MT5 Connection Badge */}
                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-sm border ${
                        isConnected
                            ? "bg-secondary-container/10 border-secondary/20"
                            : isConnecting
                            ? "bg-primary-container/10 border-primary/20"
                            : "bg-surface-container-highest border-outline-variant/20"
                    }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${
                            isConnected ? "bg-secondary animate-pulse" : isConnecting ? "bg-primary animate-bounce" : "bg-outline flex-shrink-0"
                        }`}></div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${
                            isConnected ? "text-secondary" : isConnecting ? "text-primary" : "text-on-surface-variant"
                        }`}>
                            {isConnected ? "MT5 Connected" : isConnecting ? "Connecting..." : "MT5 Disconnected"}
                        </span>
                    </div>
                    {/* Live Badge */}
                    {isConnected && (
                        <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-primary-container/10 border border-primary/20">
                            <span className="text-[10px] font-bold text-primary uppercase tracking-wider">
                                Live
                            </span>
                        </div>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-4">
                {/* Signal Icons */}
                <div className="hidden md:flex items-center gap-2 pr-4 border-r border-outline-variant/15">
                    <button className="p-2 text-on-surface-variant hover:text-on-surface transition-colors" title="Engine Status">
                        <span className="material-symbols-outlined text-[20px]">signal_cellular_alt</span>
                    </button>
                    <button className="p-2 text-on-surface-variant hover:text-on-surface transition-colors" title="Webhooks">
                        <span className="material-symbols-outlined text-[20px]">sensors</span>
                    </button>
                </div>

                {/* Kill Switch */}
                <button className="bg-tertiary-container text-on-tertiary-container px-3 py-1.5 md:px-4 md:py-2 rounded-md text-[10px] md:text-xs font-bold uppercase tracking-wider hover:opacity-90 transition-all kill-switch-glow">
                    <span className="hidden md:inline">Global </span>Kill Switch
                </button>

                {/* User Avatar */}
                <Link href="/profile" className="w-8 h-8 rounded-full bg-surface-container-highest overflow-hidden border border-outline-variant/30 flex items-center justify-center hover:ring-2 hover:ring-primary/30 transition-all shrink-0">
                    {user?.avatar_url ? (
                        <img src={user.avatar_url} alt="" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                    ) : (
                        <span className="text-xs font-bold text-primary">
                            {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "U"}
                        </span>
                    )}
                </Link>
            </div>
        </header>
    );
}
