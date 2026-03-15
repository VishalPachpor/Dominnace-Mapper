"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";
import { Users, ServerOff, Bot as BotIcon, Activity } from "lucide-react";
import { toast } from "react-hot-toast";

interface AdminStats {
  active_bots: number;
  connected_users: number;
  disconnected_users: number;
  total_users: number;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const { data } = await api.get("/admin/stats");
      setStats(data);
    } catch (error) {
      console.error("Failed to load admin stats", error);
      toast.error("Failed to load cluster statistics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 overflow-auto bg-background p-6 lg:p-10">
      <div className="max-w-6xl mx-auto space-y-8">
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-text-primary tracking-tight">Cluster Overview</h1>
            <p className="text-text-secondary mt-1 text-sm max-w-2xl leading-relaxed">
              Global system statistics, active multi-tenant connections, and trading bots.
            </p>
          </div>
          <button 
            onClick={() => {
              fetchStats().then(() => toast.success("Stats refreshed"));
            }}
            disabled={loading}
            title="Refresh Stats"
            className="flex items-center gap-2 justify-center py-2 px-4 rounded-md bg-surface border border-border text-sm font-medium text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-text-secondary border-t-transparent rounded-full animate-spin" />
            ) : (
              <Activity className="w-4 h-4" />
            )}
            <span>{loading ? "Refreshing..." : "Refresh"}</span>
          </button>
        </header>

        {loading && !stats ? (
          <div className="flex items-center justify-center p-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : stats ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            
            {/* Total Users */}
            <div className="bg-surface rounded-xl border border-border p-5 relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-text-secondary mb-1">Total Users</p>
                  <h3 className="text-3xl font-semibold text-text-primary tracking-tight">{stats.total_users}</h3>
                </div>
                <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
                  <Users className="w-5 h-5 text-blue-400" />
                </div>
              </div>
            </div>

            {/* Connected Users */}
            <div className="bg-surface rounded-xl border border-border p-5 relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-text-secondary mb-1">Connected Users</p>
                  <h3 className="text-3xl font-semibold text-green-400 tracking-tight">{stats.connected_users}</h3>
                </div>
                <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-green-400" />
                </div>
              </div>
              <div className="mt-3 text-xs text-text-tertiary">
                Subscribed & active EA/MetaApi
              </div>
            </div>

            {/* Disconnected Users */}
            <div className="bg-surface rounded-xl border border-border p-5 relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-text-secondary mb-1">Disconnected</p>
                  <h3 className="text-3xl font-semibold text-orange-400 tracking-tight">{stats.disconnected_users}</h3>
                </div>
                <div className="w-10 h-10 rounded-full bg-orange-500/10 flex items-center justify-center">
                  <ServerOff className="w-5 h-5 text-orange-400" />
                </div>
              </div>
              <div className="mt-3 text-xs text-text-tertiary">
                Requires user setup action
              </div>
            </div>

            {/* Active Bots */}
            <div className="bg-surface rounded-xl border border-border p-5 relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-text-secondary mb-1">Live AI Bots</p>
                  <h3 className="text-3xl font-semibold text-purple-400 tracking-tight">{stats.active_bots}</h3>
                </div>
                <div className="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center">
                  <BotIcon className="w-5 h-5 text-purple-400" />
                </div>
              </div>
            </div>

          </div>
        ) : (
           <div className="bg-surface rounded-xl border border-border p-10 text-center">
             <ServerOff className="w-8 h-8 text-text-tertiary mx-auto mb-3" />
             <p className="text-text-secondary">Unable to connect to the administration cluster.</p>
           </div>
        )}
      </div>
    </div>
  );
}
