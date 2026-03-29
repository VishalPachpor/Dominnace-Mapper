"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import api from "@/services/api";

const navItems = [
    { href: "/admin", label: "Overview", icon: "dashboard" },
    { href: "/admin/users", label: "Users", icon: "group" },
    { href: "/admin/trades", label: "Trades", icon: "history" },
    { href: "/admin/strategies", label: "Strategies", icon: "monitoring" },
    { href: "/admin/plans", label: "Plans", icon: "payments" },
    { href: "/admin/system", label: "System Health", icon: "health_and_safety" },
];

export default function AdminSidebar({ onClose }: { onClose?: () => void }) {
    const pathname = usePathname();
    const router = useRouter();

    const isActive = (path: string) => pathname === path;

    const linkClass = (path: string) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors group ${
            isActive(path)
                ? "bg-primary/10 text-primary border border-primary/20"
                : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
        }`;

    const handleLogout = async () => {
        try { await api.post("/auth/logout"); } catch { /* best effort */ }
        if (typeof window !== "undefined") {
            localStorage.removeItem("token");
        }
        if (onClose) onClose();
        router.push("/login");
    };

    return (
        <div className="w-64 h-full bg-surface-container-low flex flex-col border-r border-outline-variant/15 shadow-2l">
            {/* Logo */}
            <div className="p-6">
                <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-2xl">admin_panel_settings</span>
                    <h1 className="text-on-surface font-bold tracking-tight text-xl">
                        Admin
                    </h1>
                </div>
                <p className="text-primary text-[10px] uppercase tracking-widest font-bold mt-1">
                    Dominance Dashboard
                </p>
            </div>

            {/* Nav */}
            <nav className="flex-1 px-3 space-y-1">
                {navItems.map((item) => (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={linkClass(item.href)}
                        onClick={onClose}
                    >
                        <span
                            className="material-symbols-outlined text-[20px]"
                            style={
                                isActive(item.href)
                                    ? { fontVariationSettings: "'FILL' 1" }
                                    : undefined
                            }
                        >
                            {item.icon}
                        </span>
                        <span className="text-sm font-medium">{item.label}</span>
                    </Link>
                ))}
            </nav>

            {/* Bottom Section */}
            <div className="p-3 border-t border-outline-variant/15 space-y-1">
                <Link
                    href="/dashboard"
                    className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors rounded-md group w-full text-left"
                    onClick={onClose}
                >
                    <span className="material-symbols-outlined text-[20px]">
                        arrow_back
                    </span>
                    <span className="text-sm font-medium">User Dashboard</span>
                </Link>
                <button
                    className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors rounded-md group w-full text-left"
                    onClick={handleLogout}
                >
                    <span className="material-symbols-outlined text-[20px]">
                        logout
                    </span>
                    <span className="text-sm font-medium">Logout</span>
                </button>
            </div>
        </div>
    );
}
