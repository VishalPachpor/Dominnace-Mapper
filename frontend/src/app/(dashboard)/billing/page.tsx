"use client";

import { useState } from "react";
import api from "@/services/api";

export default function Billing() {
    const [loading, setLoading] = useState(false);
    const [invoice, setInvoice] = useState<any>(null);

    const handleSubscribe = async (plan: string) => {
        setLoading(true);
        try {
            const res = await api.post(`/billing/create-payment?plan=${plan}&pay_currency=usdttrc20`);
            setInvoice(res.data);
        } catch (err) {
            console.error("Failed to generate crypto invoice", err);
            alert("Failed to generate crypto invoice. Check API configurations.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-7xl mx-auto flex flex-col gap-8 text-white relative">
            <div className="text-center mt-8">
                <h1 className="text-4xl font-bold tracking-tight mb-4">Choose Your Plan</h1>
                <p className="text-slate-400 text-lg max-w-2xl mx-auto">Scale your automated trading with our transparent, crypto-native subscriptions.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-4">
                {/* Starter Plan */}
                <div className="bg-slate-800 rounded-2xl p-8 border border-slate-700 shadow-sm flex flex-col">
                    <h2 className="text-xl font-bold text-slate-300 uppercase tracking-wider mb-2">Starter</h2>
                    <div className="text-4xl font-bold mb-6">$49<span className="text-lg text-slate-500 font-normal">/mo</span></div>

                    <ul className="flex flex-col gap-4 mb-8 flex-grow text-slate-300">
                        <li className="flex items-center gap-2">✓ 1 Active Bot</li>
                        <li className="flex items-center gap-2">✓ 2 Currency Pairs</li>
                        <li className="flex items-center gap-2">✓ Standard Support</li>
                    </ul>

                    <button
                        onClick={() => handleSubscribe('starter')}
                        disabled={loading}
                        className="w-full py-3 rounded-xl border border-slate-600 hover:bg-slate-700 text-white font-bold transition-colors disabled:opacity-50">
                        Pay with Crypto
                    </button>
                </div>

                {/* Pro Plan */}
                <div className="bg-gradient-to-br from-blue-900/40 to-slate-900 rounded-2xl p-8 border border-blue-500/50 shadow-lg shadow-blue-900/20 relative flex flex-col">
                    <div className="absolute top-0 right-8 transform -translate-y-1/2 bg-blue-500 text-white px-3 py-1 text-xs font-bold rounded-full uppercase tracking-wider">
                        Popular
                    </div>
                    <h2 className="text-xl font-bold text-blue-400 uppercase tracking-wider mb-2">Pro</h2>
                    <div className="text-4xl font-bold mb-6 text-white">$99<span className="text-lg text-blue-200/50 font-normal">/mo</span></div>

                    <ul className="flex flex-col gap-4 mb-8 flex-grow text-blue-100/80">
                        <li className="flex items-center gap-2">✓ 5 Active Bots</li>
                        <li className="flex items-center gap-2">✓ Unlimited Pairs</li>
                        <li className="flex items-center gap-2">✓ TradingView Webhooks</li>
                        <li className="flex items-center gap-2">✓ Priority Support</li>
                    </ul>

                    <button
                        onClick={() => handleSubscribe('pro')}
                        disabled={loading}
                        className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold transition-colors shadow-lg shadow-blue-900/50 disabled:opacity-50">
                        Pay with Crypto
                    </button>
                </div>

                {/* Elite Plan */}
                <div className="bg-slate-800 rounded-2xl p-8 border border-slate-700 shadow-sm flex flex-col">
                    <h2 className="text-xl font-bold text-slate-300 uppercase tracking-wider mb-2">Elite</h2>
                    <div className="text-4xl font-bold mb-6">$249<span className="text-lg text-slate-500 font-normal">/mo</span></div>

                    <ul className="flex flex-col gap-4 mb-8 flex-grow text-slate-300">
                        <li className="flex items-center gap-2">✓ Unlimited Bots</li>
                        <li className="flex items-center gap-2">✓ Unlimited Pairs</li>
                        <li className="flex items-center gap-2">✓ Custom API Integrations</li>
                        <li className="flex items-center gap-2">✓ 24/7 Dedicated Support</li>
                    </ul>

                    <button
                        onClick={() => handleSubscribe('elite')}
                        disabled={loading}
                        className="w-full py-3 rounded-xl border border-slate-600 hover:bg-slate-700 text-white font-bold transition-colors disabled:opacity-50">
                        Pay with Crypto
                    </button>
                </div>
            </div>

            {/* Crypto Payment Modal */}
            {invoice && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
                    <div className="bg-slate-800 p-8 rounded-2xl border border-slate-600 max-w-md w-full shadow-2xl relative">
                        <button
                            onClick={() => setInvoice(null)}
                            className="absolute top-4 right-4 text-slate-400 hover:text-white"
                        >
                            ✕
                        </button>

                        <h2 className="text-2xl font-bold text-center mb-6">Complete Payment</h2>

                        <div className="bg-slate-700/50 p-4 rounded-xl mb-6 text-center border border-slate-600">
                            <p className="text-slate-400 text-sm mb-1">Send Exactly</p>
                            <p className="text-3xl font-bold text-blue-400">{invoice.pay_amount} {invoice.pay_currency.toUpperCase()}</p>
                        </div>

                        <div className="mb-6">
                            <p className="text-slate-400 text-sm mb-2 text-center">To Wallet Address</p>
                            <div className="bg-slate-900 p-4 rounded-xl flex items-center justify-between border border-slate-700">
                                <code className="text-sm text-green-400 break-all border-none font-mono">
                                    {invoice.pay_address}
                                </code>
                            </div>
                            <p className="text-xs text-center text-slate-500 mt-2">Make sure to select the correct network.</p>
                        </div>

                        <div className="animate-pulse bg-blue-500/10 text-blue-400 text-sm p-4 rounded-xl text-center border border-blue-500/20">
                            Awaiting blockchain confirmation... Your account will automatically activate when the transaction completes.
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
