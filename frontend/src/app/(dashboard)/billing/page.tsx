"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";

interface Subscription {
    plan: string;
    status: string;
    current_period_end: string | null;
    payment_currency?: string;
}

export default function BillingPage() {
    const [sub, setSub] = useState<Subscription>({ plan: "free", status: "none", current_period_end: null });
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState<string | null>(null);

    useEffect(() => {
        api.get("/billing/subscription")
            .then(res => setSub(res.data))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    const processPayment = async (plan: string) => {
        setProcessing(plan);
        try {
            const res = await api.post(`/billing/create-payment?plan=${plan}&pay_currency=usdt`);
            const data = res.data;
            if (data.invoice_url) {
                window.open(data.invoice_url, "_blank");
            } else if (data.payment_url) {
                window.open(data.payment_url, "_blank");
            } else {
                alert(`Redirecting to crypto payment... Invoice ID: ${data.payment_id}`);
            }
        } catch (err: any) {
            console.error("Payment creation failed", err);
            alert("Payment failed: " + (err.response?.data?.detail || err.message));
        } finally {
            setProcessing(null);
        }
    };

    const getPlanName = () => {
        if (!sub.plan || sub.plan === "free") return "Free Tier";
        return sub.plan.charAt(0).toUpperCase() + sub.plan.slice(1) + " Tier";
    };

    const isPlanActive = (planName: string) => {
        return sub.plan === planName.toLowerCase() && sub.status === "active";
    };

    return (
        <div className="flex flex-col gap-8">
            {/* ─── Current Subscription Banner ─── */}
            <div className="bg-surface-container-low rounded-xl border border-outline-variant/5 p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Active Subscription</span>
                        <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-sm ${
                            sub.status === "active" ? "bg-secondary-container text-on-secondary-fixed" : 
                            sub.status === "pending" ? "bg-primary-container text-on-primary-container" :
                            "bg-surface-container-high text-on-surface-variant"
                        }`}>
                            {sub.status.toUpperCase() || "NONE"}
                        </span>
                    </div>
                    <h2 className="text-3xl font-bold text-on-surface mb-1">
                        {loading ? "Loading..." : getPlanName()}
                    </h2>
                    <p className="text-xs text-on-surface-variant mb-4">
                        {sub.plan === "pro" ? "Advanced institutional-grade tools with sub-ms execution." : 
                         sub.plan === "elite" ? "Enterprise scale for hedge funds." : 
                         sub.plan === "starter" ? "For individual traders starting out." :
                         "Your subscription controls the limits and features available to your account."}
                    </p>
                    {sub.status === 'active' && (
                        <button className="px-4 py-2 bg-surface-container-high text-on-surface-variant text-[10px] font-bold uppercase tracking-wider rounded hover:bg-surface-container-highest transition-colors">
                            Manage Renewal
                        </button>
                    )}
                </div>
                <div className="flex items-center gap-8">
                    <div className="text-center">
                        <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Next Billing Cycle</p>
                        <p className="text-xl font-bold text-on-surface">
                            {sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : "—"}
                        </p>
                    </div>
                </div>
                <div className="bg-surface-container rounded-lg p-4">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Payment Method</p>
                    <p className="text-lg font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary">currency_bitcoin</span>
                        USDT (TRC20)
                    </p>
                    <p className="text-[10px] text-on-surface-variant mt-1 flex items-center gap-1">
                        <span className="material-symbols-outlined text-[14px]">lock</span>
                        Secured by NOWPayments
                    </p>
                </div>
            </div>

            {/* ─── Available Tiers ─── */}
            <div>
                <h3 className="text-lg font-bold text-on-surface mb-4">Available Tiers</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Starter */}
                    <div className={`bg-surface-container-low rounded-xl border p-6 flex flex-col relative ${
                        isPlanActive('starter') ? 'border-primary/50 ring-1 ring-primary/20' : 'border-outline-variant/5'
                    }`}>
                        {isPlanActive('starter') && (
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-primary-container text-on-primary-container text-[9px] font-bold uppercase tracking-wider rounded-full">
                                Current Plan
                            </div>
                        )}
                        <h4 className="text-sm font-bold text-on-surface">Starter</h4>
                        <p className="text-xs text-on-surface-variant mt-1 mb-4">For individual traders starting out.</p>
                        <p className="text-3xl font-bold text-on-surface mb-6">
                            $49 <span className="text-sm font-normal text-on-surface-variant">/month</span>
                        </p>
                        <div className="flex-1 space-y-3 mb-6">
                            <Feature text="2 Trading Bots" />
                            <Feature text="Standard Execution" />
                            <Feature text="Email Support" />
                        </div>
                        <button 
                            disabled={isPlanActive('starter') || processing !== null}
                            onClick={() => processPayment('starter')}
                            className={`w-full py-2.5 text-[10px] font-bold uppercase tracking-wider rounded transition-colors ${
                                isPlanActive('starter') ? 'bg-surface-container-highest text-on-surface-variant cursor-not-allowed' : 'bg-surface-container-high text-on-surface hover:bg-surface-container-highest'
                            }`}
                        >
                            {processing === 'starter' ? 'Processing...' : isPlanActive('starter') ? 'Active Plan' : 'Switch Plan'}
                        </button>
                    </div>

                    {/* Pro */}
                    <div className={`bg-surface-container-low rounded-xl border p-6 flex flex-col relative ${
                        isPlanActive('pro') ? 'border-primary/80 ring-2 ring-primary/30' : 'border-outline-variant/10'
                    }`}>
                        {isPlanActive('pro') && (
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-primary-container text-on-primary-container text-[9px] font-bold uppercase tracking-wider rounded-full">
                                Current Plan
                            </div>
                        )}
                        <h4 className="text-sm font-bold text-on-surface">Pro</h4>
                        <p className="text-xs text-on-surface-variant mt-1 mb-4">High-performance trading automation.</p>
                        <p className="text-3xl font-bold text-on-surface mb-6">
                            $99 <span className="text-sm font-normal text-on-surface-variant">/month</span>
                        </p>
                        <div className="flex-1 space-y-3 mb-6">
                            <Feature text="Unlimited Trading Bots" />
                            <Feature text="Sub-ms Low Latency" />
                            <Feature text="Priority Webhook Access" />
                            <Feature text="24/7 VIP Support" />
                        </div>
                        <button 
                            disabled={isPlanActive('pro') || processing !== null}
                            onClick={() => processPayment('pro')}
                            className={`w-full py-2.5 text-[10px] font-bold uppercase tracking-wider rounded transition-all ${
                                isPlanActive('pro') ? 'bg-surface-container-highest text-on-surface-variant cursor-not-allowed' : 'bg-primary-container text-on-primary-container hover:opacity-90'
                            }`}
                        >
                            {processing === 'pro' ? 'Processing...' : isPlanActive('pro') ? 'Active Plan' : 'Switch Plan'}
                        </button>
                    </div>

                    {/* Elite */}
                    <div className={`bg-surface-container-low rounded-xl border p-6 flex flex-col relative ${
                        isPlanActive('elite') ? 'border-primary/50 ring-1 ring-primary/20' : 'border-outline-variant/5'
                    }`}>
                        {isPlanActive('elite') && (
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-primary-container text-on-primary-container text-[9px] font-bold uppercase tracking-wider rounded-full">
                                Current Plan
                            </div>
                        )}
                        <h4 className="text-sm font-bold text-on-surface">Elite</h4>
                        <p className="text-xs text-on-surface-variant mt-1 mb-4">Enterprise scale for hedge funds.</p>
                        <p className="text-3xl font-bold text-on-surface mb-6">
                            $249 <span className="text-sm font-normal text-on-surface-variant">/month</span>
                        </p>
                        <div className="flex-1 space-y-3 mb-6">
                            <Feature text="Custom API endpoints" />
                            <Feature text="Dedicated Server Instance" />
                            <Feature text="On-chain Analytics" />
                            <Feature text="Direct Phone Support" />
                        </div>
                        <button 
                            disabled={isPlanActive('elite') || processing !== null}
                            onClick={() => processPayment('elite')}
                            className={`w-full py-2.5 text-[10px] font-bold uppercase tracking-wider rounded transition-colors ${
                                isPlanActive('elite') ? 'bg-surface-container-highest text-on-surface-variant cursor-not-allowed' : 'bg-surface-container-high text-on-surface hover:bg-surface-container-highest'
                            }`}
                        >
                            {processing === 'elite' ? 'Processing...' : isPlanActive('elite') ? 'Active Plan' : 'Switch Plan'}
                        </button>
                    </div>
                </div>
            </div>

            {/* ─── Payment History (Placeholder for now) ─── */}
            <div>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-bold text-on-surface">Payment History</h3>
                    <button className="text-xs text-primary hover:underline flex items-center gap-1">
                        Download All
                        <span className="material-symbols-outlined text-[14px]">download</span>
                    </button>
                </div>
                <div className="bg-surface-container-low rounded-xl overflow-hidden">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/10">
                                <th className="py-3 px-6 font-medium">Description</th>
                                <th className="py-3 px-4 font-medium">Status</th>
                                <th className="py-3 px-4 font-medium">Date</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-outline-variant/5">
                            <tr>
                                <td colSpan={3} className="py-8 text-center text-sm text-on-surface-variant">
                                    No recent transactions found.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

function Feature({ text }: { text: string }) {
    return (
        <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                check_circle
            </span>
            <span className="text-xs text-on-surface-variant">{text}</span>
        </div>
    );
}
