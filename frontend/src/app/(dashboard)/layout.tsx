"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";

export default function DashboardLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    const [sidebarOpen, setSidebarOpen] = useState(false);

    return (
        <div className="flex flex-col h-screen bg-slate-950">
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
                    <Sidebar onClose={() => setSidebarOpen(false)} />
                </div>
                
                <main className="flex-1 overflow-y-auto p-4 md:p-6 w-full">
                    {children}
                </main>
            </div>
        </div>
    );
}
