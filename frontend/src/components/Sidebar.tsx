"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
    { href: "/positions", label: "Positions", icon: "bar_chart" },
    { href: "/trades", label: "History", icon: "history" },
    { href: "/settings", label: "Accounts", icon: "manage_accounts" },
    { href: "/billing", label: "Billing", icon: "payments" },
    { href: "/admin", label: "Admin", icon: "admin_panel_settings" },
];

const bottomItems = [
    { href: "/strategy", label: "Strategy", icon: "smart_toy" },
    { href: "/profile", label: "Profile", icon: "person" },
];

export default function Sidebar({ onClose }: { onClose?: () => void }) {
    const pathname = usePathname();
    const router = useRouter();

    const isActive = (path: string) => pathname === path;

    const linkClass = (path: string) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors group ${
            isActive(path)
                ? "bg-surface-container-highest text-primary"
                : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
        }`;

    const handleLogout = () => {
        if (typeof window !== "undefined") {
            localStorage.removeItem("token");
        }
        if (onClose) onClose();
        router.push("/login");
    };

    return (
        <div className="w-64 h-full bg-surface-container-low flex flex-col border-r border-outline-variant/15 shadow-2xl md:shadow-none">
            {/* Logo */}
            <div className="p-6">
                <h1 className="text-on-surface font-bold tracking-tight text-xl">
                    DominanceBot
                </h1>
                <p className="text-on-surface-variant text-[10px] uppercase tracking-widest font-medium">
                    Trading Platform
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
                {bottomItems.map((item) => (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={linkClass(item.href)}
                        onClick={onClose}
                    >
                        <span className="material-symbols-outlined text-[20px]">
                            {item.icon}
                        </span>
                        <span className="text-sm font-medium">{item.label}</span>
                    </Link>
                ))}
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
