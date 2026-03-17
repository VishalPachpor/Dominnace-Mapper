"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import AdminSidebar from "@/components/AdminSidebar";
import Topbar from "@/components/Topbar";
import api from "@/services/api";

export default function AdminLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [isAuthorized, setIsAuthorized] = useState(false);
    const router = useRouter();

    useEffect(() => {
        const token = localStorage.getItem("token");
        if (!token) {
            router.push("/login");
            return;
        }

        api.get("/users/me")
            .then(() => setIsAuthorized(true))
            .catch((err: unknown) => {
                const status = (err as { response?: { status?: number } })?.response?.status;
                if (status === 401) {
                    localStorage.removeItem("token");
                    router.push("/login");
                    return;
                }
                setIsAuthorized(true);
            });
    }, [router]);

    if (!isAuthorized) {
        return <div className="h-screen bg-surface flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>;
    }

    return (
        <div className="flex flex-col h-screen bg-surface overflow-hidden">
            <Topbar toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
            <div className="flex flex-1 overflow-hidden relative">
                {/* Mobile overlay */}
                {sidebarOpen && (
                    <div
                        className="absolute inset-0 bg-black/50 z-20 md:hidden"
                        onClick={() => setSidebarOpen(false)}
                    />
                )}

                {/* Sidebar */}
                <div className={`absolute inset-y-0 left-0 transform ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} md:relative md:translate-x-0 transition duration-200 ease-in-out z-30 md:z-auto h-full`}>
                    <AdminSidebar onClose={() => setSidebarOpen(false)} />
                </div>

                <main className="flex-1 flex flex-col min-w-0 bg-surface">
                    <div className="flex-1 overflow-y-auto p-4 md:p-6 custom-scrollbar">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
