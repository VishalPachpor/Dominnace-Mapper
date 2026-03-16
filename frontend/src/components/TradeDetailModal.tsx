"use client";

import { useEffect, useRef } from "react";

interface Trade {
    id: string;
    symbol: string;
    side: string;
    entry_price: number;
    exit_price: number | null;
    current_price?: number;
    pnl: number;
    result: string;
    created_at: string;
    volume?: number;
    status?: string;
    commission?: number;
    swap?: number;
    deal_id?: string;
    broker_time?: string;
    source?: string;
}

interface TradeDetailModalProps {
    open: boolean;
    trade: Trade | null;
    onClose: () => void;
}

export default function TradeDetailModal({
    open,
    trade,
    onClose,
}: TradeDetailModalProps) {
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        document.addEventListener("keydown", handleKey);
        return () => document.removeEventListener("keydown", handleKey);
    }, [open, onClose]);

    if (!open || !trade) return null;

    const isWin = trade.result === "WIN";
    const statusColor = trade.status === "open" ? "text-primary" : isWin ? "text-secondary" : "text-tertiary";
    
    const details = [
        { label: "Status", value: trade.status === "open" ? "LIVE" : trade.result || "CLOSED", color: statusColor },
        { label: "Symbol", value: trade.symbol },
        { label: "Side", value: trade.side?.toUpperCase() === "BUY" ? "LONG" : "SHORT", color: trade.side?.toUpperCase() === "BUY" ? "text-secondary" : "text-tertiary" },
        { label: "Volume", value: `${trade.volume || 0.01} lots` },
        { label: "Entry Price", value: trade.entry_price || "—" },
        { label: "Exit Price", value: trade.exit_price || "—" },
        { label: "Commission", value: trade.commission !== undefined ? `$${trade.commission.toFixed(2)}` : "—" },
        { label: "Swap", value: trade.swap !== undefined ? `$${trade.swap.toFixed(2)}` : "—" },
        { label: "Net PnL", value: `$${trade.pnl.toFixed(2)}`, color: statusColor },
        { label: "Deal ID", value: trade.deal_id || "—" },
        { label: "Opened At", value: trade.created_at ? new Date(trade.created_at).toLocaleString() : "—" },
        { label: "Broker Time", value: trade.broker_time || "—" },
        { label: "Source", value: trade.source || "—" },
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-[fadeIn_150ms_ease-out]"
                onClick={onClose}
            />

            {/* panel */}
            <div
                ref={panelRef}
                tabIndex={-1}
                className="relative w-full max-w-lg mx-4 bg-surface-container rounded-2xl border border-outline-variant/10 shadow-2xl animate-[scaleIn_200ms_ease-out] outline-none overflow-hidden"
            >
                <div className="p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                <span className="material-symbols-outlined text-primary text-xl">receipt_long</span>
                            </div>
                            <div>
                                <h3 className="text-base font-bold text-on-surface">Trade Details</h3>
                                <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
                                    ID: {trade.id}
                                </p>
                            </div>
                        </div>
                        <button 
                            onClick={onClose}
                            className="w-8 h-8 rounded-lg hover:bg-surface-container-high flex items-center justify-center text-on-surface-variant transition-colors"
                        >
                            <span className="material-symbols-outlined text-lg">close</span>
                        </button>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        {details.map((d, i) => (
                            <div key={i} className="bg-surface-container-high/40 p-3 rounded-xl border border-outline-variant/5">
                                <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">
                                    {d.label}
                                </p>
                                <p className={`text-sm font-bold font-mono ${d.color || "text-on-surface"}`}>
                                    {d.value}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="px-6 pb-6 mt-2">
                    <button
                        onClick={onClose}
                        className="w-full py-3 text-sm font-bold text-on-surface bg-surface-container-high rounded-xl hover:bg-surface-container-highest transition-colors"
                    >
                        Close Details
                    </button>
                </div>
            </div>

            <style jsx>{`
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes scaleIn {
                    from { opacity: 0; transform: scale(0.95) translateY(8px); }
                    to { opacity: 1; transform: scale(1) translateY(0); }
                }
            `}</style>
        </div>
    );
}
