"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";

export default function StatusFooter() {
    const [time, setTime] = useState("");
    const [latency, setLatency] = useState<number | null>(null);

    useEffect(() => {
        const updateTime = () => {
            const now = new Date();
            setTime(now.toLocaleTimeString("en-US", { hour12: false }));
        };
        updateTime();
        const interval = setInterval(updateTime, 1000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        const measureLatency = async () => {
            try {
                const start = performance.now();
                await api.get("/users/mt-status"); // Simple cheap endpoint to ping
                const end = performance.now();
                setLatency(Math.round(end - start));
            } catch {
                setLatency(null);
            }
        };
        measureLatency();
        const interval = setInterval(measureLatency, 30000);
        return () => clearInterval(interval);
    }, []);

    return (
        <footer className="h-8 bg-surface-container-lowest flex items-center justify-between px-6 border-t border-outline-variant/15 shrink-0">
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-secondary"></div>
                    <span className="text-[9px] font-medium text-on-surface-variant uppercase tracking-wider">
                        Engine: v2.4.1 Stable
                    </span>
                </div>
                <div className="flex items-center gap-1.5 border-l border-outline-variant/15 pl-4">
                    <span className="text-[9px] font-medium text-on-surface-variant uppercase tracking-wider">
                        API: {latency !== null ? `${latency}ms` : "—"}
                    </span>
                </div>
            </div>
            <div className="flex items-center gap-4">
                <span className="text-[9px] font-mono text-on-surface-variant uppercase tracking-wider">
                    Local: {time}
                </span>
            </div>
        </footer>
    );
}
