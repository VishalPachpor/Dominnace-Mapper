"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

type MtStatus = "disconnected" | "connecting" | "deploying" | "connected" | "error" | "";

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
    disconnected: { label: "Disconnected",  color: "text-on-surface-variant",  dot: "bg-outline" },
    connecting:   { label: "Connecting…",   color: "text-primary",            dot: "bg-primary animate-pulse" },
    deploying:    { label: "Deploying…",    color: "text-primary",            dot: "bg-primary animate-pulse" },
    connected:    { label: "Connected",     color: "text-secondary",          dot: "bg-secondary" },
    error:        { label: "Error",         color: "text-tertiary",           dot: "bg-tertiary" },
};

const SUPPORTED_BROKERS = [
    { label: "Fusion Markets (Demo)", server: "FusionMarkets-Demo" },
    { label: "Fusion Markets (Live)", server: "FusionMarkets-Live" },
    { label: "IC Markets (Demo)",     server: "ICMarketsSC-Demo" },
    { label: "IC Markets (Live)",     server: "ICMarketsSC-MT5-2" },
    { label: "Exness (Demo)",         server: "Exness Technologies Ltd-Demo" },
    { label: "Exness (Live)",         server: "Exness Technologies Ltd-Real" },
    { label: "Other (enter manually)", server: "" },
];

export default function Settings() {
    const [apiKey, setApiKey] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [binanceStatus, setBinanceStatus] = useState("");

    const [mtLogin, setMtLogin] = useState("");
    const [mtPassword, setMtPassword] = useState("");
    const [mtServer, setMtServer] = useState("");
    const [mtBroker, setMtBroker] = useState("");
    const [selectedBroker, setSelectedBroker] = useState("");
    const [mtStatus, setMtStatus] = useState<MtStatus>("");
    const [mtConnectMsg, setMtConnectMsg] = useState("");
    const [isConnecting, setIsConnecting] = useState(false);
    const [existingLogin, setExistingLogin] = useState<string | null>(null);

    const fetchMtStatus = useCallback(async () => {
        try {
            const res = await api.get("/users/mt-status");
            setMtStatus(res.data.mt_status || "disconnected");
            if (res.data.mt_login) setExistingLogin(res.data.mt_login);
        } catch { /* not connected yet */ }
    }, []);

    useEffect(() => { fetchMtStatus(); }, [fetchMtStatus]);

    useEffect(() => {
        if (mtStatus !== "connecting" && mtStatus !== "deploying") return;
        const interval = setInterval(async () => {
            const res = await api.get("/users/mt-status");
            const newStatus: MtStatus = res.data.mt_status || "disconnected";
            setMtStatus(newStatus);
            if (newStatus === "connected") {
                setMtConnectMsg("MT5 terminal is live! Trades will now execute automatically.");
                clearInterval(interval);
            } else if (newStatus === "error") {
                setMtConnectMsg("Connection failed. Check your credentials and try again.");
                clearInterval(interval);
            }
        }, 10000);
        return () => clearInterval(interval);
    }, [mtStatus]);

    const handleBrokerSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const found = SUPPORTED_BROKERS.find(b => b.label === e.target.value);
        setSelectedBroker(e.target.value);
        setMtBroker(e.target.value);
        setMtServer(found?.server || "");
    };

    const connectMT5 = async () => {
        if (!mtLogin || !mtPassword || !mtServer) {
            setMtConnectMsg("Please fill in all fields.");
            return;
        }
        setIsConnecting(true);
        setMtConnectMsg("");
        try {
            await api.post("/users/connect-mt5", {
                mt_login: mtLogin, mt_password: mtPassword,
                mt_server: mtServer, mt_broker: mtBroker || selectedBroker,
            });
            setMtStatus("deploying");
            setMtConnectMsg("Cloud terminal is starting up. This takes ~90 seconds…");
        } catch (err: any) {
            setMtStatus("error");
            setMtConnectMsg(err?.response?.data?.detail || "Connection failed.");
        } finally {
            setIsConnecting(false);
        }
    };

    const saveKeys = async () => {
        try {
            await api.post("/users/add-api-key", { api_key: apiKey, secret_key: secretKey });
            setBinanceStatus("Keys saved successfully!");
        } catch {
            setBinanceStatus("Failed to save keys.");
        }
    };

    const statusCfg = STATUS_CONFIG[mtStatus] || STATUS_CONFIG["disconnected"];

    const inputClass = "w-full p-3 bg-surface-container-lowest border border-outline-variant/20 rounded-md text-on-surface text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all font-mono";

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-on-surface">Broker Management</h1>
                    <p className="text-xs text-on-surface-variant mt-1">
                        Provision and monitor high-frequency trading gateways.
                    </p>
                </div>
                <button className="flex items-center gap-2 px-4 py-2 bg-primary-container text-on-primary-container rounded-md text-[10px] font-bold uppercase tracking-wider hover:opacity-90 transition-all">
                    <span className="material-symbols-outlined text-[18px]">add</span>
                    Add New Broker Account
                </button>
            </div>

            {/* ─── MT5 Broker Card ─── */}
            <div className="bg-surface-container-low rounded-xl border border-outline-variant/5 overflow-hidden">
                <div className="p-6 flex flex-col lg:flex-row gap-6">
                    {/* Main Card Content */}
                    <div className="flex-1">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-primary text-2xl">account_balance</span>
                                <div>
                                    <h3 className="text-sm font-bold text-on-surface">MT5 Cloud Terminal</h3>
                                    <p className="text-[10px] text-on-surface-variant font-mono">
                                        {existingLogin ? `Login: ${existingLogin}` : "Not connected"}
                                    </p>
                                </div>
                            </div>
                            <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-sm border ${
                                mtStatus === "connected"
                                    ? "bg-secondary-container/10 border-secondary/20"
                                    : mtStatus === "error"
                                    ? "bg-tertiary-container/10 border-tertiary/20"
                                    : "bg-surface-container-high border-outline-variant/20"
                            }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`}></div>
                                <span className={`text-[10px] font-bold uppercase tracking-wider ${statusCfg.color}`}>
                                    {statusCfg.label}
                                </span>
                            </div>
                        </div>

                        {mtConnectMsg && (
                            <div className={`text-xs mb-4 p-3 rounded-md border ${
                                mtStatus === "connected" ? "bg-secondary-container/10 border-secondary/20 text-secondary"
                                : mtStatus === "error" ? "bg-tertiary-container/10 border-tertiary/20 text-tertiary"
                                : "bg-primary-container/10 border-primary/20 text-primary"
                            }`}>
                                {mtConnectMsg}
                            </div>
                        )}

                        <div className="flex flex-col gap-4">
                            <label className="flex flex-col gap-1.5">
                                <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Broker</span>
                                <select
                                    id="broker-select"
                                    className={inputClass}
                                    value={selectedBroker}
                                    onChange={handleBrokerSelect}
                                >
                                    <option value="">Select your broker…</option>
                                    {SUPPORTED_BROKERS.map(b => (
                                        <option key={b.label} value={b.label}>{b.label}</option>
                                    ))}
                                </select>
                            </label>

                            <label className="flex flex-col gap-1.5">
                                <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Server</span>
                                <input
                                    id="mt5-server"
                                    className={inputClass}
                                    placeholder="e.g. FusionMarkets-Demo"
                                    value={mtServer}
                                    onChange={e => setMtServer(e.target.value)}
                                />
                            </label>

                            <div className="grid grid-cols-2 gap-4">
                                <label className="flex flex-col gap-1.5">
                                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Login ID</span>
                                    <input
                                        id="mt5-login"
                                        className={inputClass}
                                        placeholder="e.g. 279223"
                                        value={mtLogin}
                                        onChange={e => setMtLogin(e.target.value)}
                                    />
                                </label>
                                <label className="flex flex-col gap-1.5">
                                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Password</span>
                                    <input
                                        id="mt5-password"
                                        type="password"
                                        className={inputClass}
                                        placeholder="••••••••"
                                        value={mtPassword}
                                        onChange={e => setMtPassword(e.target.value)}
                                    />
                                </label>
                            </div>
                        </div>

                        <button
                            id="connect-mt5-btn"
                            className="mt-6 w-full py-3 bg-primary-container text-on-primary-container font-bold rounded-md text-xs uppercase tracking-wider hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                            onClick={connectMT5}
                            disabled={isConnecting || mtStatus === "connected"}
                        >
                            {isConnecting ? "Connecting…" : mtStatus === "connected" ? "Broker Connected" : "Connect MT5 Account"}
                        </button>
                        <p className="text-[10px] text-on-surface-variant mt-2 text-center">
                            Your password is AES-256 encrypted before storage.
                        </p>
                    </div>

                    {/* Active Operations Panel */}
                    <div className="lg:w-72 bg-surface-container rounded-lg p-4 flex flex-col gap-3">
                        <h4 className="text-xs font-bold text-on-surface uppercase tracking-wider">Active Operations</h4>
                        <div className="flex items-center justify-between p-3 bg-surface-container-high rounded-md">
                            <div>
                                <p className="text-[10px] font-bold text-on-surface">MetaApi Provisioning</p>
                                <p className="text-[10px] text-on-surface-variant">Cloud MT5 Gateway</p>
                            </div>
                            <span className="text-[10px] font-bold text-secondary">
                                {mtStatus === "connected" ? "100%" : mtStatus === "deploying" ? "75%" : "—"}
                            </span>
                        </div>
                        <div className="flex items-center justify-between p-3 bg-surface-container-high rounded-md">
                            <p className="text-[10px] font-bold text-on-surface">Syncing History</p>
                            <span className="text-[10px] text-on-surface-variant">Pending</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* ─── Binance Card ─── */}
            <div className="bg-surface-container-low rounded-xl border border-outline-variant/5 p-6">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <span className="material-symbols-outlined text-primary">currency_bitcoin</span>
                        <div>
                            <h3 className="text-sm font-bold text-on-surface">Binance Unified</h3>
                            <p className="text-[10px] text-on-surface-variant">Spot / Futures Gateway</p>
                        </div>
                    </div>
                    <span className="px-2 py-0.5 bg-surface-container-high rounded text-[10px] font-bold text-on-surface-variant uppercase">
                        Binance
                    </span>
                </div>

                {binanceStatus && (
                    <p className={`text-xs mb-4 ${binanceStatus.includes("success") ? "text-secondary" : "text-tertiary"}`}>
                        {binanceStatus}
                    </p>
                )}

                <div className="flex flex-col gap-4 max-w-xl">
                    <label className="flex flex-col gap-1.5">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">API Key</span>
                        <input className={inputClass} placeholder="Enter public api key" onChange={e => setApiKey(e.target.value)} />
                    </label>
                    <label className="flex flex-col gap-1.5">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Secret Key</span>
                        <input type="password" className={inputClass} placeholder="••••••••••••••••" onChange={e => setSecretKey(e.target.value)} />
                    </label>
                </div>

                <button
                    className="mt-6 px-6 py-3 bg-primary-container text-on-primary-container font-bold rounded-md text-xs uppercase tracking-wider hover:opacity-90 transition-all"
                    onClick={saveKeys}
                >
                    Securely Save Credentials
                </button>
            </div>

            {/* ─── Security Section ─── */}
            <div className="bg-surface-container-low rounded-xl border border-outline-variant/5 p-6">
                <h3 className="text-sm font-bold text-on-surface mb-1">Security & Access Control</h3>
                <p className="text-xs text-on-surface-variant mb-6">
                    Manage your JWT session tokens and global access permissions. Credentials are encrypted using AES-256-GCM before storage.
                </p>
                <div className="flex items-center gap-3">
                    <button className="px-4 py-2 bg-primary-container text-on-primary-container rounded-md text-[10px] font-bold uppercase tracking-wider hover:opacity-90 transition-all">
                        Rotate JWT Secrets
                    </button>
                    <button className="px-4 py-2 bg-tertiary-container text-on-tertiary-container rounded-md text-[10px] font-bold uppercase tracking-wider hover:opacity-90 transition-all">
                        Revoke All Active Sessions
                    </button>
                </div>
            </div>
        </div>
    );
}
