"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";

interface AdminUser {
    id: string;
    email: string;
    status: string;
    plan: string;
    created_at: string;
    last_login: string | null;
    total_trades: number;
    total_pnl: number;
}

export default function AdminUsers() {
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");

    const fetchUsers = useCallback(async () => {
        try {
            const res = await api.get("/admin/users");
            setUsers(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error("Failed to fetch users", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchUsers();
    }, [fetchUsers]);

    const filteredUsers = users.filter((u) =>
        u.email.toLowerCase().includes(search.toLowerCase())
    );

    const getStatusColor = (status: string) => {
        switch (status?.toLowerCase()) {
            case "active": return "text-secondary bg-secondary/10";
            case "suspended": return "text-tertiary bg-tertiary/10";
            case "pending": return "text-primary bg-primary/10";
            default: return "text-on-surface-variant bg-surface-container-high";
        }
    };

    return (
        <div className="flex flex-col gap-6">
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-on-surface">User Management</h1>
                    <p className="text-sm text-on-surface-variant">Monitor and manage all platform accounts.</p>
                </div>
                <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">search</span>
                    <input
                        type="text"
                        placeholder="Search by email..."
                        className="bg-surface-container-high border border-outline-variant/10 rounded-lg pl-10 pr-4 py-2 text-sm text-on-surface focus:outline-none focus:ring-1 focus:ring-primary w-full md:w-64"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
            </header>

            <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] text-on-surface-variant uppercase tracking-widest border-b border-outline-variant/5">
                                <th className="py-4 px-6 font-medium">Account</th>
                                <th className="py-4 px-6 font-medium">Status</th>
                                <th className="py-4 px-6 font-medium">Plan</th>
                                <th className="py-4 px-6 font-medium text-right">Performance</th>
                                <th className="py-4 px-6 font-medium text-right">Activity</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-outline-variant/5">
                            {loading ? (
                                <tr>
                                    <td colSpan={5} className="py-12 text-center text-sm text-on-surface-variant">
                                        <div className="flex flex-col items-center gap-2">
                                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                            Loading users...
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredUsers.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="py-12 text-center text-sm text-on-surface-variant">
                                        No users found matching your search.
                                    </td>
                                </tr>
                            ) : (
                                filteredUsers.map((u) => (
                                    <tr key={u.id} className="hover:bg-surface-container-high/30 transition-colors group">
                                        <td className="py-4 px-6">
                                            <div className="flex flex-col">
                                                <span className="text-sm font-bold text-on-surface">{u.email}</span>
                                                <span className="text-[10px] text-on-surface-variant">ID: {u.id.substring(0, 8)}...</span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6">
                                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${getStatusColor(u.status)}`}>
                                                {u.status || "PENDING"}
                                            </span>
                                        </td>
                                        <td className="py-4 px-6">
                                            <span className="text-sm text-on-surface">{u.plan}</span>
                                        </td>
                                        <td className="py-4 px-6 text-right">
                                            <div className="flex flex-col items-end">
                                                <span className={`text-sm font-bold ${u.total_pnl >= 0 ? "text-secondary" : "text-tertiary"}`}>
                                                    {u.total_pnl >= 0 ? "+" : ""}{u.total_pnl.toFixed(2)}
                                                </span>
                                                <span className="text-[10px] text-on-surface-variant">
                                                    {u.total_trades} trades
                                                </span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6 text-right">
                                            <div className="flex flex-col items-end">
                                                <span className="text-[10px] text-on-surface-variant font-mono">
                                                    Last: {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                                                </span>
                                                <span className="text-[10px] text-on-surface-variant font-mono">
                                                    Join: {u.created_at ? new Date(u.created_at).toLocaleDateString() : "N/A"}
                                                </span>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
