"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

type MtStatus = "disconnected" | "connecting" | "deploying" | "connected" | "error" | "";

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
    disconnected: { label: "Disconnected",  color: "text-slate-400",  dot: "bg-slate-500" },
    connecting:   { label: "Connecting…",   color: "text-yellow-400", dot: "bg-yellow-400 animate-pulse" },
    deploying:    { label: "Deploying…",    color: "text-blue-400",   dot: "bg-blue-400 animate-pulse" },
    connected:    { label: "Connected",     color: "text-emerald-400",dot: "bg-emerald-400" },
    error:        { label: "Error",         color: "text-red-400",    dot: "bg-red-500" },
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
    // ── Binance Keys ──────────────────────────────────────────────────────────
    const [apiKey, setApiKey] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [binanceStatus, setBinanceStatus] = useState("");

    // ── MT5 MetaApi Connect ───────────────────────────────────────────────────
    const [mtLogin, setMtLogin] = useState("");
    const [mtPassword, setMtPassword] = useState("");
    const [mtServer, setMtServer] = useState("");
    const [mtBroker, setMtBroker] = useState("");
    const [selectedBroker, setSelectedBroker] = useState("");
    const [mtStatus, setMtStatus] = useState<MtStatus>("");
    const [mtConnectMsg, setMtConnectMsg] = useState("");
    const [isConnecting, setIsConnecting] = useState(false);
    const [existingLogin, setExistingLogin] = useState<string | null>(null);

    // ── Load existing MT5 status on mount ─────────────────────────────────────
    const fetchMtStatus = useCallback(async () => {
        try {
            const res = await api.get("/users/mt-status");
            setMtStatus(res.data.mt_status || "disconnected");
            if (res.data.mt_login) setExistingLogin(res.data.mt_login);
        } catch {
            // not connected yet
        }
    }, []);

    useEffect(() => {
        fetchMtStatus();
    }, [fetchMtStatus]);

    // ── Poll status every 10s while deploying / connecting ────────────────────
    useEffect(() => {
        if (mtStatus !== "connecting" && mtStatus !== "deploying") return;
        const interval = setInterval(async () => {
            const res = await api.get("/users/mt-status");
            const newStatus: MtStatus = res.data.mt_status || "disconnected";
            setMtStatus(newStatus);
            if (newStatus === "connected") {
                setMtConnectMsg("✅ MT5 terminal is live! Trades will now execute automatically.");
                clearInterval(interval);
            } else if (newStatus === "error") {
                setMtConnectMsg("❌ Connection failed. Check your credentials and try again.");
                clearInterval(interval);
            }
        }, 10000);
        return () => clearInterval(interval);
    }, [mtStatus]);

    // ── Handlers ──────────────────────────────────────────────────────────────
    const handleBrokerSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const found = SUPPORTED_BROKERS.find(b => b.label === e.target.value);
        setSelectedBroker(e.target.value);
        setMtBroker(e.target.value);
        setMtServer(found?.server || "");
    };

    const connectMT5 = async () => {
        if (!mtLogin || !mtPassword || !mtServer) {
            setMtConnectMsg("⚠️ Please fill in all fields.");
            return;
        }
        setIsConnecting(true);
        setMtConnectMsg("");
        try {
            await api.post("/users/connect-mt5", {
                mt_login: mtLogin,
                mt_password: mtPassword,
                mt_server: mtServer,
                mt_broker: mtBroker || selectedBroker,
            });
            setMtStatus("deploying");
            setMtConnectMsg("⏳ Cloud terminal is starting up. This takes ~90 seconds…");
        } catch (err: any) {
            setMtStatus("error");
            setMtConnectMsg("❌ " + (err?.response?.data?.detail || "Connection failed."));
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

    return (
        <div className="max-w-7xl mx-auto flex flex-col gap-6 text-white">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Exchange Settings</h1>
                <p className="text-slate-400 mt-1">Configure your broker and API connectivity securely.</p>
            </div>

            {/* ── MetaApi MT5 Connect Card ── */}
            <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 w-full max-w-2xl shadow-sm">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-2">Connect MT5 Broker</h2>
                        <p className="text-sm text-slate-400">
                            Your broker credentials are AES-encrypted and stored securely. Trades will execute
                            automatically on your account via a cloud MT5 terminal — no desktop app required.
                        </p>
                    </div>
                    <span className="bg-slate-900 border border-slate-700 px-3 py-1 rounded text-xs font-bold text-blue-400">MT5 CLOUD</span>
                </div>

                {/* Status Badge */}
                <div className="flex items-center gap-2 mb-6 p-3 bg-slate-900 rounded-xl border border-slate-700">
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${statusCfg.dot}`} />
                    <span className={`text-sm font-semibold ${statusCfg.color}`}>{statusCfg.label}</span>
                    {existingLogin && mtStatus === "connected" && (
                        <span className="ml-auto text-xs text-slate-400 font-mono">Login: {existingLogin}</span>
                    )}
                </div>

                {mtConnectMsg && (
                    <p className={`text-sm mb-4 ${mtConnectMsg.startsWith("✅") ? "text-emerald-400" : mtConnectMsg.startsWith("❌") ? "text-red-400" : "text-yellow-400"}`}>
                        {mtConnectMsg}
                    </p>
                )}

                <div className="flex flex-col gap-5">
                    {/* Broker Dropdown */}
                    <label className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Broker</span>
                        <select
                            id="broker-select"
                            className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                            value={selectedBroker}
                            onChange={handleBrokerSelect}
                        >
                            <option value="">Select your broker…</option>
                            {SUPPORTED_BROKERS.map(b => (
                                <option key={b.label} value={b.label}>{b.label}</option>
                            ))}
                        </select>
                    </label>

                    {/* Server (auto-filled but editable) */}
                    <label className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Server</span>
                        <input
                            id="mt5-server"
                            className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm"
                            placeholder="e.g. FusionMarkets-Demo"
                            value={mtServer}
                            onChange={e => setMtServer(e.target.value)}
                        />
                    </label>

                    <div className="grid grid-cols-2 gap-4">
                        {/* Login */}
                        <label className="flex flex-col gap-2">
                            <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Login ID</span>
                            <input
                                id="mt5-login"
                                className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm"
                                placeholder="e.g. 279223"
                                value={mtLogin}
                                onChange={e => setMtLogin(e.target.value)}
                            />
                        </label>

                        {/* Password */}
                        <label className="flex flex-col gap-2">
                            <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Password</span>
                            <input
                                id="mt5-password"
                                type="password"
                                className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                                placeholder="••••••••"
                                value={mtPassword}
                                onChange={e => setMtPassword(e.target.value)}
                            />
                        </label>
                    </div>
                </div>

                <button
                    id="connect-mt5-btn"
                    className="mt-8 px-6 py-3 w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-colors shadow-lg shadow-blue-900/20"
                    onClick={connectMT5}
                    disabled={isConnecting || mtStatus === "connected"}
                >
                    {isConnecting ? "Connecting…" : mtStatus === "connected" ? "✅ Broker Connected" : "🔗 Connect MT5 Account"}
                </button>

                <p className="text-xs text-slate-500 mt-3 text-center">
                    🔒 Your password is AES-256 encrypted before storage. Disable withdrawal permissions on your broker account for safety.
                </p>
            </div>

            {/* ── Binance API Keys Card ── */}
            <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 w-full max-w-2xl shadow-sm">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-2">Binance API Credentials</h2>
                        <p className="text-sm text-slate-400">For crypto trading. Ensure keys only have spot trading permission with IP whitelisting.</p>
                    </div>
                    <span className="bg-slate-900 border border-slate-700 px-3 py-1 rounded text-xs font-bold text-slate-300">BINANCE</span>
                </div>

                {binanceStatus && <p className={`text-sm mb-4 ${binanceStatus.includes("success") ? "text-green-500" : "text-red-500"}`}>{binanceStatus}</p>}

                <div className="flex flex-col gap-5">
                    <label className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">API Key</span>
                        <input className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm" placeholder="Enter public api key" onChange={e => setApiKey(e.target.value)} />
                    </label>
                    <label className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Secret Key</span>
                        <input type="password" className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm" placeholder="••••••••••••••••••••••••••••••••" onChange={e => setSecretKey(e.target.value)} />
                    </label>
                </div>

                <button className="mt-8 px-6 py-3 w-full bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-colors shadow-lg shadow-blue-900/20" onClick={saveKeys}>
                    Securely Save Credentials
                </button>
            </div>
        </div>
    );
}
