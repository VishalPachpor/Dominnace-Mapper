"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Sidebar({ onClose }: { onClose?: () => void }) {
    const pathname = usePathname();

    const isActive = (path: string) => pathname === path;

    const linkClass = (path: string) =>
        `p-3 rounded-xl transition-colors font-medium ${isActive(path) ? 'bg-blue-600 shadow-lg shadow-blue-900/20 text-white' : 'hover:bg-slate-800 text-slate-400 hover:text-white'}`;

    return (
        <div className="w-64 h-full bg-slate-900 border-r border-slate-800 text-white flex flex-col p-4 shadow-2xl md:shadow-none">
            <nav className="flex flex-col gap-2 flex-grow mt-2">
                <span className="text-xs uppercase font-bold text-slate-500 tracking-wider mb-2 px-3">Menu</span>
                <Link href="/dashboard" className={linkClass("/dashboard")} onClick={onClose}>
                    Dashboard
                </Link>
                <Link href="/positions" className={linkClass("/positions")} onClick={onClose}>
                    Positions
                </Link>
                <Link href="/trades" className={linkClass("/trades")} onClick={onClose}>
                    Trade History
                </Link>

                <div className="mt-8"></div>
                <span className="text-xs uppercase font-bold text-slate-500 tracking-wider mb-2 px-3">Account</span>
                <Link href="/settings" className={linkClass("/settings")} onClick={onClose}>
                    API Settings
                </Link>
                <Link href="/billing" className={linkClass("/billing")} onClick={onClose}>
                    Billing & Plans
                </Link>
            </nav>

            <div className="mt-auto border-t border-slate-800 pt-4">
                <button className="w-full text-left p-3 text-slate-400 hover:text-red-400 hover:bg-slate-800/50 rounded-xl transition-colors font-medium">
                    Logout
                </button>
            </div>
        </div>
    );
}
