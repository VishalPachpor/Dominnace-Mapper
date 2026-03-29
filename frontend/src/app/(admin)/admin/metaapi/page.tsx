"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/services/api";

interface ScoreBreakdown {
    connected?: number;
    account_data?: number;
    recent_activity?: number;
    positions?: number;
    preferred?: number;
}

interface MetaApiAccount {
    id: string;
    state: string;
    score: number;
    score_breakdown?: ScoreBreakdown;
    selection_reason?: {
        has_account_data?: boolean;
        is_live?: boolean;
        has_open_positions?: boolean;
        is_preferred?: boolean;
    } | null;
    is_canonical: boolean;
    linked_user_id: string | null;
    has_account_data: boolean;
    has_open_positions: boolean;
    recent_activity: boolean;
    age_minutes: number | null;
    cleanup_candidate: boolean;
    cleanup_reason: string | null;
}

interface MetaApiGroup {
    key: string;
    login: string;
    server: string;
    canonical_account_id: string | null;
    accounts: MetaApiAccount[];
    summary: {
        total_accounts: number;
        active_accounts: number;
        cleanup_candidates: number;
    };
}

interface MetaApiResponse {
    groups: MetaApiGroup[];
    last_evaluated_at?: string;
    is_snapshot?: boolean;
}

interface ReEvaluateResponse {
    status: string;
    forced: boolean;
    evaluated_at?: string;
    groups_count?: number;
    rebinds_triggered?: number;
    cleanup_actions?: number;
    duration_ms?: number;
    retry_after_seconds?: number;
}

type FilterMode = "all" | "cleanup" | "multi" | "inactive";

function scoreTone(score: number) {
    if (score >= 80) return "bg-secondary";
    if (score >= 50) return "bg-primary";
    return "bg-tertiary";
}

function accountTone(account: MetaApiAccount) {
    if (account.is_canonical) return "border-secondary/25 bg-secondary/5";
    if (account.cleanup_candidate) return "border-tertiary/25 bg-tertiary/5";
    return "border-primary/15 bg-surface-container";
}

function stateTone(state: string) {
    const normalized = state.toUpperCase();
    if (normalized.includes("CONNECTED") || normalized.includes("DEPLOYED")) {
        return "bg-secondary/10 text-secondary";
    }
    if (normalized.includes("DISCONNECTED") || normalized.includes("UNDEPLOY")) {
        return "bg-outline-variant/20 text-on-surface-variant";
    }
    return "bg-tertiary/10 text-tertiary";
}

export default function AdminMetaApiPage() {
    const [groups, setGroups] = useState<MetaApiGroup[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [filter, setFilter] = useState<FilterMode>("all");
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const [lastEvaluatedAt, setLastEvaluatedAt] = useState<string | null>(null);
    const [isSnapshot, setIsSnapshot] = useState(false);
    const [reEvaluating, setReEvaluating] = useState(false);
    const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

    const fetchGroups = useCallback(async (silent = false) => {
        if (silent) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }

        try {
            const res = await api.get<MetaApiResponse>("/admin/system/metaapi/accounts");
            const nextGroups = Array.isArray(res.data?.groups) ? res.data.groups : [];
            setLastEvaluatedAt(res.data?.last_evaluated_at || null);
            setIsSnapshot(Boolean(res.data?.is_snapshot));
            setGroups(nextGroups);
            setExpanded((prev) => {
                const next = { ...prev };
                for (const group of nextGroups) {
                    if (next[group.key] === undefined) {
                        next[group.key] = group.summary.total_accounts > 1 || group.summary.cleanup_candidates > 0;
                    }
                }
                return next;
            });
        } catch (err) {
            console.error("Failed to fetch MetaApi account groups", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        fetchGroups();
        const interval = setInterval(() => fetchGroups(true), 30000);
        return () => clearInterval(interval);
    }, [fetchGroups]);

    const totals = useMemo(() => {
        const multiAccountGroups = groups.filter((group) => group.summary.total_accounts > 1).length;
        const cleanupCandidates = groups.reduce((sum, group) => sum + group.summary.cleanup_candidates, 0);
        const inactiveGroups = groups.filter((group) => group.summary.active_accounts === 0).length;
        const activeGroups = groups.filter((group) => group.summary.active_accounts > 0).length;
        const brokenCanonicalGroups = groups.filter((group) => {
            const canonicalCount = group.accounts.filter((account) => account.is_canonical).length;
            return canonicalCount !== 1;
        }).length;
        return { multiAccountGroups, cleanupCandidates, inactiveGroups, activeGroups, brokenCanonicalGroups };
    }, [groups]);

    const filteredGroups = useMemo(() => {
        return groups.filter((group) => {
            if (filter === "cleanup") return group.summary.cleanup_candidates > 0;
            if (filter === "multi") return group.summary.total_accounts > 1;
            if (filter === "inactive") return group.summary.active_accounts === 0;
            return true;
        });
    }, [filter, groups]);

    const toggleExpanded = (key: string) => {
        setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
    };

    useEffect(() => {
        if (!toast) return;
        const timeout = setTimeout(() => setToast(null), 3500);
        return () => clearTimeout(timeout);
    }, [toast]);

    const handleReEvaluate = async () => {
        setReEvaluating(true);
        try {
            const res = await api.post<ReEvaluateResponse>("/admin/system/metaapi/re-evaluate");
            if (res.data.status !== "ok") {
                const retry = res.data.retry_after_seconds;
                setToast({
                    msg: retry
                        ? `Re-evaluate cooling down. Try again in ${retry}s.`
                        : "Re-evaluate is already running.",
                    type: "error",
                });
                return;
            }
            setToast({
                msg: `Re-evaluated: ${res.data.rebinds_triggered ?? 0} rebind${(res.data.rebinds_triggered ?? 0) === 1 ? "" : "s"}, ${res.data.cleanup_actions ?? 0} cleanup action${(res.data.cleanup_actions ?? 0) === 1 ? "" : "s"} in ${res.data.duration_ms ?? 0}ms.`,
                type: "success",
            });
            await fetchGroups(true);
        } catch (err) {
            console.error("Failed to re-evaluate MetaApi groups", err);
            setToast({ msg: "Re-evaluate failed. Check admin logs.", type: "error" });
        } finally {
            setReEvaluating(false);
        }
    };

    return (
        <div className="flex flex-col gap-6">
            <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-on-surface">MetaApi Accounts</h1>
                    <p className="text-sm text-on-surface-variant">
                        Inspect canonical account selection, duplicate terminals, and cleanup candidates in real time.
                    </p>
                    {lastEvaluatedAt && (
                        <p className="text-[11px] text-on-surface-variant mt-2">
                            Last evaluated: {new Date(lastEvaluatedAt).toLocaleString("en-IN", {
                                year: "numeric",
                                month: "short",
                                day: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                                hour12: true,
                                timeZone: "Asia/Kolkata",
                            })}
                            {isSnapshot ? " (cached)" : " (fresh)"}
                        </p>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex bg-surface-container rounded-lg p-1 overflow-x-auto">
                        {[
                            { value: "all", label: "All" },
                            { value: "cleanup", label: "Cleanup" },
                            { value: "multi", label: "Multi-Account" },
                            { value: "inactive", label: "Inactive" },
                        ].map((item) => (
                            <button
                                key={item.value}
                                onClick={() => setFilter(item.value as FilterMode)}
                                className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider whitespace-nowrap transition-all ${
                                    filter === item.value
                                        ? "bg-primary text-on-primary shadow-sm"
                                        : "text-on-surface-variant hover:text-on-surface"
                                }`}
                            >
                                {item.label}
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={handleReEvaluate}
                        disabled={reEvaluating}
                        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                            reEvaluating
                                ? "bg-surface-container text-on-surface-variant cursor-not-allowed"
                                : "bg-primary text-on-primary hover:opacity-90"
                        }`}
                    >
                        <span className={`material-symbols-outlined text-[18px] ${reEvaluating ? "animate-spin" : ""}`}>
                            sync
                        </span>
                        {reEvaluating ? "Re-Evaluating" : "Re-Evaluate Now"}
                    </button>
                    <button
                        onClick={() => fetchGroups(true)}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-bold uppercase tracking-wider transition-colors"
                    >
                        <span className={`material-symbols-outlined text-[18px] ${refreshing ? "animate-spin" : ""}`}>refresh</span>
                        Refresh
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
                <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                    <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Groups</div>
                    <div className="mt-2 text-2xl font-bold text-on-surface">{groups.length}</div>
                    <div className="mt-1 text-[10px] text-on-surface-variant">{totals.activeGroups} with active terminals</div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                    <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Multi-Account</div>
                    <div className="mt-2 text-2xl font-bold text-on-surface">{totals.multiAccountGroups}</div>
                    <div className="mt-1 text-[10px] text-on-surface-variant">Duplicate login/server groups</div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                    <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Cleanup Candidates</div>
                    <div className="mt-2 text-2xl font-bold text-tertiary">{totals.cleanupCandidates}</div>
                    <div className="mt-1 text-[10px] text-on-surface-variant">Safe undeploy-only candidates</div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                    <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Inactive Groups</div>
                    <div className="mt-2 text-2xl font-bold text-primary">{totals.inactiveGroups}</div>
                    <div className="mt-1 text-[10px] text-on-surface-variant">No live healthy terminals</div>
                </div>
                <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                    <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Canonical Alerts</div>
                    <div className="mt-2 text-2xl font-bold text-tertiary">{totals.brokenCanonicalGroups}</div>
                    <div className="mt-1 text-[10px] text-on-surface-variant">Groups with zero or multiple canonicals</div>
                </div>
            </div>

            {(totals.multiAccountGroups > 0 || totals.cleanupCandidates > 0 || totals.inactiveGroups > 0 || totals.brokenCanonicalGroups > 0) && (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                        <div className="flex items-start gap-3">
                            <span className="material-symbols-outlined text-primary">hub</span>
                            <div>
                                <div className="text-sm font-bold text-on-surface">Duplicate Terminal Watch</div>
                                <div className="text-xs text-on-surface-variant mt-1">
                                    {totals.multiAccountGroups} group{totals.multiAccountGroups === 1 ? "" : "s"} currently have multiple MetaApi terminals.
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="rounded-xl border border-tertiary/20 bg-tertiary/5 p-4">
                        <div className="flex items-start gap-3">
                            <span className="material-symbols-outlined text-tertiary">warning</span>
                            <div>
                                <div className="text-sm font-bold text-on-surface">Cleanup Queue</div>
                                <div className="text-xs text-on-surface-variant mt-1">
                                    {totals.cleanupCandidates} terminal{totals.cleanupCandidates === 1 ? "" : "s"} are eligible for safe undeploy cleanup.
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="rounded-xl border border-outline-variant/20 bg-surface-container p-4">
                        <div className="flex items-start gap-3">
                            <span className="material-symbols-outlined text-on-surface-variant">signal_disconnected</span>
                            <div>
                                <div className="text-sm font-bold text-on-surface">Inactive Groups</div>
                                <div className="text-xs text-on-surface-variant mt-1">
                                    {totals.inactiveGroups} group{totals.inactiveGroups === 1 ? "" : "s"} have no active terminals and may need review.
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="rounded-xl border border-tertiary/20 bg-tertiary/5 p-4">
                        <div className="flex items-start gap-3">
                            <span className="material-symbols-outlined text-tertiary">rule</span>
                            <div>
                                <div className="text-sm font-bold text-on-surface">Canonical Invariant</div>
                                <div className="text-xs text-on-surface-variant mt-1">
                                    {totals.brokenCanonicalGroups} group{totals.brokenCanonicalGroups === 1 ? "" : "s"} currently break the one-canonical rule.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="flex flex-col gap-4">
                {toast && (
                    <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${
                        toast.type === "error"
                            ? "bg-tertiary-container text-on-tertiary-container"
                            : "bg-secondary-container text-on-secondary-container"
                    }`}>
                        {toast.msg}
                    </div>
                )}
                {loading ? (
                    <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 p-12 text-center">
                        <div className="flex flex-col items-center gap-3">
                            <div className="h-8 w-8 rounded-full border-b-2 border-primary animate-spin" />
                            <div className="text-sm text-on-surface-variant">Inspecting MetaApi terminal groups...</div>
                        </div>
                    </div>
                ) : filteredGroups.length === 0 ? (
                    <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 p-12 text-center text-sm text-on-surface-variant">
                        No MetaApi groups matched this filter.
                    </div>
                ) : (
                    filteredGroups.map((group) => {
                        const isExpanded = !!expanded[group.key];
                        const canonicalCount = group.accounts.filter((account) => account.is_canonical).length;
                        const hasCanonicalIssue = canonicalCount !== 1;
                        return (
                            <section
                                key={group.key}
                                className="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden"
                            >
                                <button
                                    onClick={() => toggleExpanded(group.key)}
                                    className="w-full px-6 py-5 text-left hover:bg-surface-container/40 transition-colors"
                                >
                                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
                                        <div className="lg:col-span-4">
                                            <div className="text-sm font-bold text-on-surface">{group.login}</div>
                                            <div className="text-xs text-on-surface-variant mt-1">{group.server}</div>
                                        </div>
                                        <div className="lg:col-span-3">
                                            <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Canonical</div>
                                            <div className="mt-1 text-xs font-mono text-secondary break-all">
                                                {group.canonical_account_id || "Unavailable"}
                                            </div>
                                        </div>
                                        <div className="lg:col-span-3 grid grid-cols-3 gap-3">
                                            <div>
                                                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Total</div>
                                                <div className="mt-1 text-sm font-bold text-on-surface">{group.summary.total_accounts}</div>
                                            </div>
                                            <div>
                                                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Active</div>
                                                <div className="mt-1 text-sm font-bold text-secondary">{group.summary.active_accounts}</div>
                                            </div>
                                            <div>
                                                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Cleanup</div>
                                                <div className="mt-1 text-sm font-bold text-tertiary">{group.summary.cleanup_candidates}</div>
                                            </div>
                                        </div>
                                        <div className="lg:col-span-2 flex items-center justify-between lg:justify-end gap-3">
                                            {group.summary.cleanup_candidates > 0 && (
                                                <span className="px-2 py-1 rounded-full bg-tertiary/10 text-tertiary text-[10px] font-bold uppercase tracking-wider">
                                                    Cleanup
                                                </span>
                                            )}
                                            {group.summary.total_accounts > 1 && (
                                                <span className="px-2 py-1 rounded-full bg-primary/10 text-primary text-[10px] font-bold uppercase tracking-wider">
                                                    Duplicate
                                                </span>
                                            )}
                                            {hasCanonicalIssue && (
                                                <span className="px-2 py-1 rounded-full bg-tertiary/10 text-tertiary text-[10px] font-bold uppercase tracking-wider">
                                                    Canonical Alert
                                                </span>
                                            )}
                                            <span className="material-symbols-outlined text-on-surface-variant">
                                                {isExpanded ? "expand_less" : "expand_more"}
                                            </span>
                                        </div>
                                    </div>
                                </button>

                                {isExpanded && (
                                    <div className="px-6 pb-6">
                                        {hasCanonicalIssue && (
                                            <div className="mb-4 rounded-xl border border-tertiary/20 bg-tertiary/5 p-4">
                                                <div className="flex items-start gap-3">
                                                    <span className="material-symbols-outlined text-tertiary">warning</span>
                                                    <div>
                                                        <div className="text-sm font-bold text-on-surface">Broken Canonical Invariant</div>
                                                        <div className="text-xs text-on-surface-variant mt-1">
                                                            This group currently has {canonicalCount} canonical account{canonicalCount === 1 ? "" : "s"}.
                                                            Expected exactly one canonical terminal.
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                                            {group.accounts.map((account) => (
                                                <div
                                                    key={account.id}
                                                    className={`rounded-xl border p-5 ${accountTone(account)}`}
                                                >
                                                    <div className="flex flex-col gap-4">
                                                        <div className="flex items-start justify-between gap-4">
                                                            <div>
                                                                <div className="flex items-center gap-2 flex-wrap">
                                                                    <span className="text-sm font-mono font-bold text-on-surface break-all">{account.id}</span>
                                                                    {account.is_canonical && (
                                                                        <span className="px-2 py-0.5 rounded-full bg-secondary/10 text-secondary text-[10px] font-bold uppercase tracking-wider">
                                                                            Canonical
                                                                        </span>
                                                                    )}
                                                                    {account.cleanup_candidate && (
                                                                        <span className="px-2 py-0.5 rounded-full bg-tertiary/10 text-tertiary text-[10px] font-bold uppercase tracking-wider">
                                                                            Cleanup Candidate
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <div className="mt-2 flex items-center gap-2 flex-wrap">
                                                                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${stateTone(account.state)}`}>
                                                                        {account.state}
                                                                    </span>
                                                                    {account.linked_user_id && (
                                                                        <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-bold uppercase tracking-wider">
                                                                            Linked User
                                                                        </span>
                                                                    )}
                                                                    {account.has_open_positions && (
                                                                        <span className="px-2 py-0.5 rounded-full bg-secondary/10 text-secondary text-[10px] font-bold uppercase tracking-wider">
                                                                            Open Positions
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                            <div className="text-right min-w-[112px]">
                                                                <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Score</div>
                                                                <div className="mt-1 text-lg font-bold text-on-surface">{account.score}</div>
                                                            </div>
                                                        </div>

                                                        <div>
                                                            <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                                                                <span>Health Score</span>
                                                                <span>{account.score}/100</span>
                                                            </div>
                                                            <div className="h-2 rounded-full bg-surface-container-highest overflow-hidden">
                                                                <div
                                                                    className={`h-full transition-all duration-500 ${scoreTone(account.score)}`}
                                                                    style={{ width: `${Math.max(4, Math.min(account.score, 100))}%` }}
                                                                />
                                                            </div>
                                                        </div>

                                                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                                            <div className="rounded-lg bg-surface-container-high/70 p-3">
                                                                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Linked User</div>
                                                                <div className="mt-2 text-sm font-medium text-on-surface break-all">
                                                                    {account.linked_user_id || "Unlinked"}
                                                                </div>
                                                            </div>
                                                            <div className="rounded-lg bg-surface-container-high/70 p-3">
                                                                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Activity</div>
                                                                <div className="mt-2 text-sm font-medium text-on-surface">
                                                                    {account.recent_activity ? "Recent" : "Quiet"}
                                                                </div>
                                                            </div>
                                                            <div className="rounded-lg bg-surface-container-high/70 p-3">
                                                                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Account Data</div>
                                                                <div className="mt-2 text-sm font-medium text-on-surface">
                                                                    {account.has_account_data ? "Present" : "Missing"}
                                                                </div>
                                                            </div>
                                                            <div className="rounded-lg bg-surface-container-high/70 p-3">
                                                                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Age</div>
                                                                <div className="mt-2 text-sm font-medium text-on-surface">
                                                                    {account.age_minutes === null ? "Unknown" : `${account.age_minutes}m`}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <div className="rounded-lg bg-surface-container-high/70 p-4">
                                                            <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold mb-3">
                                                                Score Breakdown
                                                            </div>
                                                            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                                                                {[
                                                                    ["Connected", account.score_breakdown?.connected ?? 0],
                                                                    ["Account Data", account.score_breakdown?.account_data ?? 0],
                                                                    ["Recent Activity", account.score_breakdown?.recent_activity ?? 0],
                                                                    ["Positions", account.score_breakdown?.positions ?? 0],
                                                                    ["Preferred", account.score_breakdown?.preferred ?? 0],
                                                                ].map(([label, value]) => (
                                                                    <div key={label} className="rounded-lg bg-surface p-3 border border-outline-variant/10">
                                                                        <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">{label}</div>
                                                                        <div className="mt-2 text-sm font-bold text-on-surface">{value}</div>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>

                                                        {account.selection_reason && (
                                                            <div className="rounded-lg bg-surface-container-high/70 p-4">
                                                                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold mb-3">
                                                                    Selection Reason
                                                                </div>
                                                                {(() => {
                                                                    const selectionRows: Array<{ label: string; enabled: boolean }> = [
                                                                        { label: "Live", enabled: Boolean(account.selection_reason?.is_live) },
                                                                        { label: "Account Data", enabled: Boolean(account.selection_reason?.has_account_data) },
                                                                        { label: "Open Positions", enabled: Boolean(account.selection_reason?.has_open_positions) },
                                                                        { label: "Preferred", enabled: Boolean(account.selection_reason?.is_preferred) },
                                                                    ];
                                                                    return (
                                                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                                                            {selectionRows.map((item) => (
                                                                                <div key={item.label} className="rounded-lg bg-surface p-3 border border-outline-variant/10">
                                                                                    <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">{item.label}</div>
                                                                                    <div className={`mt-2 text-sm font-bold ${item.enabled ? "text-secondary" : "text-on-surface-variant"}`}>
                                                                                        {item.enabled ? "Yes" : "No"}
                                                                                    </div>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    );
                                                                })()}
                                                            </div>
                                                        )}

                                                        {account.cleanup_candidate && (
                                                            <div className="rounded-lg border border-tertiary/20 bg-tertiary/5 p-4">
                                                                <div className="text-[10px] uppercase tracking-widest text-tertiary font-bold">Cleanup Reason</div>
                                                                <div className="mt-2 text-sm text-on-surface">
                                                                    {account.cleanup_reason || "Stale duplicate"}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </section>
                        );
                    })
                )}
            </div>
        </div>
    );
}
