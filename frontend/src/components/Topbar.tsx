"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import api from "@/services/api";

interface MtStatus {
    mt_status: string;
    mt_broker: string | null;
    can_trade?: boolean;
    meta_account_id?: string | null;
}

interface UserMini {
    full_name: string;
    email: string;
    avatar_url: string;
    can_trade?: boolean;
    has_mt5_key?: boolean;
    mt_status?: string;
}

export default function Topbar({ toggleSidebar }: { toggleSidebar?: () => void }) {
    const [status, setStatus] = useState<MtStatus>({ mt_status: "disconnected", mt_broker: null });
    const [user, setUser] = useState<UserMini | null>(null);

    useEffect(() => {
        const fetchStatus = () => {
            Promise.allSettled([
                api.get("/users/mt-status", { params: { _ts: Date.now() } }),
                api.get("/users/me", { params: { _ts: Date.now() } }),
            ])
                .then(([statusRes, userRes]) => {
                    const statusData = statusRes.status === "fulfilled" ? statusRes.value.data : {};
                    const userData = userRes.status === "fulfilled" ? userRes.value.data : {};

                    setStatus({
                        mt_status: statusData.mt_status || userData.mt_status || "disconnected",
                        mt_broker: statusData.mt_broker || userData.mt_broker || null,
                        can_trade:
                            typeof statusData.can_trade === "boolean"
                                ? statusData.can_trade
                                : userData.can_trade,
                        meta_account_id: statusData.meta_account_id || null,
                    });

                    if (userRes.status === "fulfilled") {
                        setUser(userData);
                    }
                })
                .catch(() => {});
        };
        fetchStatus();
        const interval = setInterval(fetchStatus, 30000);
        const onAccountStatusChanged = () => fetchStatus();
        window.addEventListener("dm:account-status-changed", onAccountStatusChanged);
        return () => {
            clearInterval(interval);
            window.removeEventListener("dm:account-status-changed", onAccountStatusChanged);
        };
    }, []);

    const canTrade = status.can_trade ?? user?.can_trade ?? true;
    const hasLinkedMtAccount = Boolean(status.meta_account_id || user?.has_mt5_key);
    const isConnected = status.mt_status === "connected" && canTrade;
    const isConnecting = status.mt_status === "connecting" || status.mt_status === "deploying";
    const isInactive = !canTrade && (hasLinkedMtAccount || status.mt_status === "connected" || user?.mt_status === "connected");

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
                            : isInactive
                            ? "bg-tertiary-container/10 border-tertiary/20"
                            : isConnecting
                            ? "bg-primary-container/10 border-primary/20"
                            : "bg-surface-container-highest border-outline-variant/20"
                    }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${
                            isConnected
                                ? "bg-secondary animate-pulse"
                                : isInactive
                                ? "bg-tertiary"
                                : isConnecting
                                ? "bg-primary animate-bounce"
                                : "bg-outline flex-shrink-0"
                        }`}></div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${
                            isConnected ? "text-secondary" : isInactive ? "text-tertiary" : isConnecting ? "text-primary" : "text-on-surface-variant"
                        }`}>
                            {isConnected ? "MT5 Connected" : isInactive ? "MT5 Inactive" : isConnecting ? "Connecting..." : "MT5 Disconnected"}
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
