"use client";

import { useState, useEffect, useId, useMemo } from "react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    CartesianGrid,
    ReferenceLine,
} from "recharts";

interface DataPoint {
    time: string;
    pnl: number;
}

interface PerformanceChartProps {
    data: DataPoint[];
    height?: number;
    showReferenceLine?: boolean;
    loading?: boolean;
}

/* ── Y-axis formatter: $1.2K, $19K, $1.2M ── */
function fmtDollar(value: number): string {
    const abs = Math.abs(value);
    const sign = value < 0 ? "-" : "";
    if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(abs >= 10_000 ? 0 : 1)}K`;
    return `${sign}$${abs.toFixed(0)}`;
}

/* ── X-axis formatter: ISO → "Mar 09", fallback to raw ── */
function fmtDate(raw: string): string {
    try {
        const d = new Date(raw);
        if (isNaN(d.getTime())) return raw;
        return d.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
    } catch {
        return raw;
    }
}

/* ── Custom Tooltip ── */
function ChartTooltip({ active, payload, startValue }: any) {
    if (!active || !payload?.[0]) return null;
    const point = payload[0].payload as DataPoint;
    const value = point.pnl;
    const pnlChange = value - startValue;
    const pctChange = startValue !== 0 ? (pnlChange / Math.abs(startValue)) * 100 : 0;
    const isUp = pnlChange >= 0;

    return (
        <div className="bg-[#0f172a] border border-slate-700 rounded-lg px-4 py-3 shadow-xl">
            <p className="text-[10px] text-slate-400 font-mono mb-1.5">{fmtDate(point.time)}</p>
            <p className="text-sm font-bold text-white">
                ${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
            <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs font-bold ${isUp ? "text-[#4edea3]" : "text-[#ffb3b0]"}`}>
                    {isUp ? "+" : ""}{pnlChange.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className={`text-[10px] font-mono ${isUp ? "text-[#4edea3]" : "text-[#ffb3b0]"}`}>
                    ({isUp ? "+" : ""}{pctChange.toFixed(2)}%)
                </span>
            </div>
        </div>
    );
}

export default function PerformanceChart({
    data,
    height = 400,
    showReferenceLine = true,
    loading = false,
}: PerformanceChartProps) {
    const [mounted, setMounted] = useState(false);
    const gradientId = useId().replace(/:/g, "_");

    useEffect(() => {
        setMounted(true);
    }, []);

    const { startValue, endValue, isProfit } = useMemo(() => {
        if (!data || data.length === 0) return { startValue: 0, endValue: 0, isProfit: true };
        const s = data[0].pnl;
        const e = data[data.length - 1].pnl;
        return { startValue: s, endValue: e, isProfit: e >= s };
    }, [data]);

    const lineColor = isProfit ? "#4edea3" : "#ffb3b0";
    const fillId = `grad_${gradientId}`;

    if (!mounted) {
        return (
            <div
                className="w-full bg-surface-container-low animate-pulse rounded-xl"
                style={{ height }}
            />
        );
    }

    if ((!data || data.length === 0) && !loading) {
        return (
            <div
                className="w-full flex items-center justify-center text-sm text-on-surface-variant"
                style={{ height }}
            >
                No chart data available
            </div>
        );
    }

    if (loading && (!data || data.length === 0)) {
        return (
            <div
                className="w-full flex items-center justify-center text-sm text-on-surface-variant"
                style={{ height }}
            >
                Loading chart data…
            </div>
        );
    }

    return (
        <ResponsiveContainer width="100%" height={height}>
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                    <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={lineColor} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
                    </linearGradient>
                </defs>

                <CartesianGrid
                    horizontal={true}
                    vertical={false}
                    strokeDasharray="3 3"
                    stroke="rgba(148,163,184,0.08)"
                />

                <XAxis
                    dataKey="time"
                    tickFormatter={fmtDate}
                    stroke="transparent"
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    dy={8}
                    interval="preserveStartEnd"
                    minTickGap={60}
                />

                <YAxis
                    orientation="right"
                    tickFormatter={fmtDollar}
                    stroke="transparent"
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    dx={4}
                    width={60}
                    domain={["auto", "auto"]}
                />

                <Tooltip
                    content={<ChartTooltip startValue={startValue} />}
                    cursor={{
                        stroke: "#64748b",
                        strokeWidth: 1,
                        strokeDasharray: "4 4",
                    }}
                />

                {showReferenceLine && data.length > 0 && (
                    <ReferenceLine
                        y={startValue}
                        stroke="#64748b"
                        strokeDasharray="6 4"
                        strokeWidth={1}
                    />
                )}

                <Area
                    type="monotone"
                    dataKey="pnl"
                    stroke={lineColor}
                    strokeWidth={2.5}
                    fill={`url(#${fillId})`}
                    dot={false}
                    activeDot={{
                        r: 5,
                        fill: lineColor,
                        stroke: "#0f172a",
                        strokeWidth: 2,
                        filter: `drop-shadow(0 0 4px ${lineColor})`,
                    }}
                />
            </AreaChart>
        </ResponsiveContainer>
    );
}
