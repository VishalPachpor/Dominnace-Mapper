"use client";

import { useEffect, useRef } from "react";

interface ConfirmModalProps {
    open: boolean;
    title: string;
    description: string;
    details?: { label: string; value: string; color?: string }[];
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: "danger" | "warning";
    loading?: boolean;
    loadingLabel?: string;
    onConfirm: () => void;
    onCancel: () => void;
}

export default function ConfirmModal({
    open,
    title,
    description,
    details,
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    variant = "danger",
    loading = false,
    loadingLabel = "Working…",
    onConfirm,
    onCancel,
}: ConfirmModalProps) {
    const panelRef = useRef<HTMLDivElement>(null);

    /* close on Escape */
    useEffect(() => {
        if (!open) return;
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !loading) onCancel();
        };
        document.addEventListener("keydown", handleKey);
        return () => document.removeEventListener("keydown", handleKey);
    }, [open, loading, onCancel]);

    /* trap focus inside panel */
    useEffect(() => {
        if (open) panelRef.current?.focus();
    }, [open]);

    if (!open) return null;

    const isDanger = variant === "danger";
    const iconBg = isDanger ? "bg-tertiary/10" : "bg-yellow-500/10";
    const iconColor = isDanger ? "text-tertiary" : "text-yellow-400";
    const btnBg = isDanger
        ? "bg-tertiary hover:bg-tertiary/90"
        : "bg-yellow-500 hover:bg-yellow-500/90";
    const btnText = isDanger ? "text-white" : "text-black";

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-[fadeIn_150ms_ease-out]"
                onClick={!loading ? onCancel : undefined}
            />

            {/* panel */}
            <div
                ref={panelRef}
                tabIndex={-1}
                className="relative w-full max-w-md mx-4 bg-surface-container rounded-2xl border border-outline-variant/10 shadow-2xl animate-[scaleIn_200ms_ease-out] outline-none"
            >
                <div className="p-6">
                    {/* icon + title */}
                    <div className="flex items-start gap-4">
                        <div className={`flex-shrink-0 w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center`}>
                            <span className={`material-symbols-outlined text-xl ${iconColor}`}>
                                {isDanger ? "warning" : "info"}
                            </span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <h3 className="text-base font-bold text-on-surface">{title}</h3>
                            <p className="mt-1 text-sm text-on-surface-variant leading-relaxed">{description}</p>
                        </div>
                    </div>

                    {/* trade details card */}
                    {details && details.length > 0 && (
                        <div className="mt-5 bg-surface-container-high/50 rounded-xl p-4 space-y-2">
                            {details.map((d, i) => (
                                <div key={i} className="flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                                        {d.label}
                                    </span>
                                    <span className={`text-sm font-bold font-mono ${d.color || "text-on-surface"}`}>
                                        {d.value}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* actions */}
                <div className="px-6 pb-6 flex items-center gap-3">
                    <button
                        onClick={onCancel}
                        disabled={loading}
                        className="flex-1 py-2.5 text-sm font-bold text-on-surface-variant bg-surface-container-high rounded-xl hover:bg-surface-container-highest transition-colors disabled:opacity-40"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={loading}
                        className={`flex-1 py-2.5 text-sm font-bold ${btnText} ${btnBg} rounded-xl transition-all disabled:opacity-60 flex items-center justify-center gap-2`}
                    >
                        {loading ? (
                            <>
                                <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                                {loadingLabel}
                            </>
                        ) : (
                            confirmLabel
                        )}
                    </button>
                </div>
            </div>

            {/* keyframe animations */}
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
