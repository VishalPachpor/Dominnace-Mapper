"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";

export default function Settings() {
    const [apiKey, setApiKey] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [status, setStatus] = useState("");

    const [eaToken, setEaToken] = useState("");
    const [eaLastSeen, setEaLastSeen] = useState<string | null>(null);
    const [eaStatus, setEaStatus] = useState("");

    useEffect(() => {
        // Fetch existing ea_token on load
        api.get("/users/ea-token")
            .then(res => {
                if (res.data.ea_token) {
                    setEaToken(res.data.ea_token);
                    setEaLastSeen(res.data.ea_last_seen);
                }
            })
            .catch(err => console.error("Could not load EA token", err));
    }, []);

    const saveKeys = async () => {
        try {
            await api.post("/users/add-api-key", { api_key: apiKey, secret_key: secretKey });
            setStatus("Keys saved successfully!");
        } catch (err) {
            setStatus("Failed to save keys.");
        }
    };

    const generateEaToken = async () => {
        try {
            const res = await api.post("/users/ea-token");
            setEaToken(res.data.ea_token);
            setEaStatus("EA Token generated successfully!");
        } catch (err) {
            setEaStatus("Failed to generate EA token.");
        }
    };

    return (
        <div className="max-w-7xl mx-auto flex flex-col gap-6 text-white">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Exchange Settings</h1>
                <p className="text-slate-400 mt-1">Configure your API connectivity securely.</p>
            </div>

            <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 w-full max-w-2xl shadow-sm">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-2">Binance API Credentials</h2>
                        <p className="text-sm text-slate-400">Ensure your keys only contain trading permissions and have IP whitelisting enabled.</p>
                    </div>
                    <span className="bg-slate-900 border border-slate-700 px-3 py-1 rounded text-xs font-bold text-slate-300">BINANCE</span>
                </div>

                {status && <p className={`text-sm ${status.includes('success') ? 'text-green-500' : 'text-red-500'}`}>{status}</p>}

                <div className="flex flex-col gap-5">
                    <label className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">API Key</span>
                        <input
                            className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm"
                            placeholder="Enter public api key"
                            onChange={e => setApiKey(e.target.value)}
                        />
                    </label>

                    <label className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Secret Key</span>
                        <input
                            type="password"
                            className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono text-sm"
                            placeholder="••••••••••••••••••••••••••••••••"
                            onChange={e => setSecretKey(e.target.value)}
                        />
                    </label>
                </div>

                <button
                    className="mt-8 px-6 py-3 w-full bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-colors shadow-lg shadow-blue-900/20"
                    onClick={saveKeys}
                >
                    Securely Save Credentials
                </button>
            </div>

            {/* MT5 EA Bridge Card */}
            <div className="bg-slate-800 p-8 rounded-2xl border border-slate-700 w-full max-w-2xl shadow-sm mt-4">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-2">MT5 Expert Advisor (Zero Cost Bridge)</h2>
                        <p className="text-sm text-slate-400">Install our custom EA into your MetaTrader 5 terminal to instantly execute Forex and Commodities signals from the cloud.</p>
                    </div>
                    <span className="bg-slate-900 border border-slate-700 px-3 py-1 rounded text-xs font-bold text-emerald-400">ACTIVE</span>
                </div>

                {eaStatus && <p className={`text-sm mb-4 ${eaStatus.includes('success') ? 'text-green-500' : 'text-red-500'}`}>{eaStatus}</p>}

                <div className="flex flex-col gap-5">
                    <div className="flex flex-col gap-2">
                        <span className="font-semibold text-sm text-slate-300 uppercase tracking-wider">Your EA Access Token</span>
                        {eaToken ? (
                            <div className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-emerald-400 font-mono text-sm break-all">
                                {eaToken}
                            </div>
                        ) : (
                            <div className="p-3 bg-slate-900 border border-slate-700 rounded-xl text-slate-500 font-mono text-sm italic">
                                No token generated yet. Click generate below.
                            </div>
                        )}
                    </div>

                    {eaLastSeen && (
                        <div className="text-xs text-slate-400">
                            <strong>Terminal Connection:</strong> Last seen polling {new Date(eaLastSeen).toLocaleString()}
                        </div>
                    )}
                </div>

                <div className="mt-8 flex gap-4">
                    <button
                        className="px-6 py-3 w-full bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-colors shadow-lg shadow-blue-900/20"
                        onClick={generateEaToken}
                    >
                        {eaToken ? "Regenerate Token" : "Generate EA Token"}
                    </button>
                    {/* In a real app we would host the .ex5 file on a CDN or serve from /public */}
                    <button
                        className="px-6 py-3 w-full bg-slate-700 hover:bg-slate-600 text-white font-bold rounded-xl transition-colors text-center shadow-lg cursor-not-allowed opacity-80"
                        title="Download will be active soon"
                    >
                        Download DominanceEA.ex5
                    </button>
                </div>
            </div>
        </div>
    );
}
