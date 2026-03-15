"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";

interface UserProfile {
    email: string;
    full_name: string;
    avatar_url: string;
    oauth_provider: string | null;
    bio: string;
    telegram_alerts: boolean;
    push_notifications: boolean;
    has_binance_key: boolean;
    binance_api_key_last4: string | null;
    has_mt5_key: boolean;
    mt_login: string | null;
    mt_server: string | null;
    mt_broker: string | null;
    mt_status: string;
    ea_token_active: boolean;
}

export default function ProfilePage() {
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Form states
    const [fullName, setFullName] = useState("");
    const [bio, setBio] = useState("");
    const [telAlerts, setTelAlerts] = useState(false);
    const [pushNotifs, setPushNotifs] = useState(false);

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const res = await api.get("/users/me");
                setProfile(res.data);
                setFullName(res.data.full_name || "");
                setBio(res.data.bio || "");
                setTelAlerts(res.data.telegram_alerts || false);
                setPushNotifs(res.data.push_notifications || false);
            } catch (err) {
                console.error("Failed to fetch profile", err);
            } finally {
                setLoading(false);
            }
        };
        fetchProfile();
    }, []);

    const handleSave = async () => {
        setSaving(true);
        try {
            await api.put("/users/me", {
                full_name: fullName,
                bio,
                telegram_alerts: telAlerts,
                push_notifications: pushNotifs,
            });
            setProfile((prev) => (prev ? { ...prev, full_name: fullName } : null));
            alert("Profile updated successfully!");
        } catch {
            alert("Failed to update profile.");
        } finally {
            setSaving(false);
        }
    };

    const handleRevokeBinance = async () => {
        if (!confirm("Are you sure you want to revoke Binance API keys?")) return;
        try {
            await api.delete("/users/api-key/binance");
            setProfile((prev) =>
                prev ? { ...prev, has_binance_key: false, binance_api_key_last4: null } : null
            );
            alert("Binance keys revoked.");
        } catch {
            alert("Failed to revoke keys.");
        }
    };

    const handleRevokeMT5 = async () => {
        if (!confirm("Are you sure you want to disconnect your MT5 terminal?")) return;
        try {
            await api.delete("/users/api-key/mt5");
            setProfile((prev) =>
                prev
                    ? { ...prev, has_mt5_key: false, mt_login: null, mt_server: null, mt_status: "disconnected" }
                    : null
            );
            alert("MT5 account disconnected.");
        } catch {
            alert("Failed to disconnect MT5.");
        }
    };

    if (loading) return <div className="p-8 text-on-surface">Loading profile...</div>;

    // Derive initials for fallback avatar
    const initials = (() => {
        if (profile?.full_name) {
            const parts = profile.full_name.trim().split(" ");
            if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
            return parts[0][0].toUpperCase();
        }
        return profile?.email?.[0]?.toUpperCase() || "U";
    })();

    const oauthLabel =
        profile?.oauth_provider === "google"
            ? "Google"
            : profile?.oauth_provider === "apple"
            ? "Apple"
            : null;

    return (
        <div className="flex flex-col gap-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-headline font-bold text-on-surface tracking-tight">
                        Profile &amp; Security
                    </h1>
                    <p className="text-on-surface-variant text-sm mt-1">
                        Manage your identity, connections, and security settings.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* ─── Profile Card ─── */}
                <section className="col-span-1 lg:col-span-8 bg-surface-container-low p-6 rounded-lg h-fit">
                    <div className="flex max-sm:flex-col gap-6 mb-6">
                        {/* Avatar */}
                        <div className="relative group shrink-0 mx-auto sm:mx-0">
                            <div className="w-24 h-24 rounded-xl overflow-hidden border border-outline-variant/10 bg-surface-container-highest flex items-center justify-center">
                                {profile?.avatar_url ? (
                                    <img
                                        src={profile.avatar_url}
                                        alt={profile.full_name || "Avatar"}
                                        className="w-full h-full object-cover"
                                        referrerPolicy="no-referrer"
                                    />
                                ) : (
                                    <span className="text-3xl font-bold text-primary">{initials}</span>
                                )}
                            </div>
                            {/* OAuth badge */}
                            {oauthLabel && (
                                <div className="absolute -bottom-2 -right-2 flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container-highest border border-outline-variant/20 shadow-lg">
                                    {profile?.oauth_provider === "google" && (
                                        <svg className="w-3 h-3" viewBox="0 0 24 24">
                                            <path
                                                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                                                fill="#4285F4"
                                            />
                                            <path
                                                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                                fill="#34A853"
                                            />
                                            <path
                                                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                                                fill="#FBBC05"
                                            />
                                            <path
                                                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                                                fill="#EA4335"
                                            />
                                        </svg>
                                    )}
                                    {profile?.oauth_provider === "apple" && (
                                        <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
                                        </svg>
                                    )}
                                    <span className="text-[8px] font-bold text-on-surface-variant uppercase tracking-wider">
                                        {oauthLabel}
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Fields */}
                        <div className="space-y-5 flex-1 w-full">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                                        Full Name
                                    </label>
                                    <input
                                        type="text"
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        placeholder="Enter your name"
                                        className="w-full bg-surface-container border border-outline-variant/15 text-on-surface focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 px-3 py-2.5 rounded-lg font-medium text-sm transition-all"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                                        Email Address
                                    </label>
                                    <div className="relative">
                                        <input
                                            type="email"
                                            value={profile?.email || ""}
                                            readOnly
                                            className="w-full bg-surface-container/50 border border-outline-variant/10 text-on-surface-variant px-3 py-2.5 rounded-lg font-medium text-sm cursor-not-allowed"
                                        />
                                        {oauthLabel && (
                                            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[9px] font-bold text-on-surface-variant/50 uppercase tracking-wider">
                                                via {oauthLabel}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                                    Professional Bio
                                </label>
                                <textarea
                                    rows={3}
                                    value={bio}
                                    onChange={(e) => setBio(e.target.value)}
                                    placeholder="Tell us about your trading journey..."
                                    className="w-full bg-surface-container border border-outline-variant/15 text-on-surface focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 px-3 py-2.5 text-sm leading-relaxed resize-none rounded-lg transition-all"
                                />
                            </div>
                        </div>
                    </div>
                    <div className="flex justify-end">
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="px-6 py-2.5 bg-primary-container text-on-primary-container font-bold text-xs rounded-lg uppercase tracking-widest hover:opacity-90 transition-all disabled:opacity-50"
                        >
                            {saving ? "Saving..." : "Save Changes"}
                        </button>
                    </div>
                </section>

                {/* ─── Platform Preferences ─── */}
                <section className="col-span-1 lg:col-span-4 bg-surface-container-low p-6 rounded-lg h-fit">
                    <h3 className="text-xs uppercase tracking-[0.2em] text-on-surface-variant font-bold mb-6 flex items-center gap-2">
                        <span className="material-symbols-outlined text-sm">tune</span> Preferences
                    </h3>

                    <div className="space-y-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-on-surface">Telegram Alerts</p>
                                <p className="text-[10px] text-on-surface-variant">Real-time trade signals</p>
                            </div>
                            <Toggle active={telAlerts} onClick={() => setTelAlerts(!telAlerts)} />
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-on-surface">Push Notifications</p>
                                <p className="text-[10px] text-on-surface-variant">Mobile execution status</p>
                            </div>
                            <Toggle active={pushNotifs} onClick={() => setPushNotifs(!pushNotifs)} />
                        </div>

                        <div className="flex items-center justify-between opacity-50">
                            <div>
                                <p className="text-sm font-medium text-on-surface">Visual Theme</p>
                                <p className="text-[10px] text-on-surface-variant">Kinetic Dark (Locked)</p>
                            </div>
                            <span className="material-symbols-outlined text-on-surface-variant text-sm">lock</span>
                        </div>
                    </div>

                    {/* Connected Account Info */}
                    {oauthLabel && (
                        <div className="mt-6 p-4 bg-surface-container rounded-lg border border-outline-variant/10">
                            <h4 className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold mb-3">
                                Connected Account
                            </h4>
                            <div className="flex items-center gap-3">
                                {profile?.avatar_url ? (
                                    <img
                                        src={profile.avatar_url}
                                        alt=""
                                        className="w-8 h-8 rounded-full"
                                        referrerPolicy="no-referrer"
                                    />
                                ) : (
                                    <div className="w-8 h-8 rounded-full bg-surface-container-highest flex items-center justify-center">
                                        <span className="text-xs font-bold text-primary">{initials}</span>
                                    </div>
                                )}
                                <div className="min-w-0">
                                    <p className="text-sm font-medium text-on-surface truncate">
                                        {profile?.full_name || profile?.email}
                                    </p>
                                    <p className="text-[10px] text-on-surface-variant truncate">{profile?.email}</p>
                                </div>
                                <div className="ml-auto shrink-0">
                                    <span className="px-2 py-0.5 bg-secondary-container/20 text-secondary text-[8px] font-bold uppercase tracking-wider rounded">
                                        Linked
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                </section>

                {/* ─── Account Security ─── */}
                <section className="col-span-1 lg:col-span-6 space-y-5">
                    <div className="bg-surface-container-low p-6 rounded-lg">
                        <h3 className="text-xs uppercase tracking-[0.2em] text-on-surface-variant font-bold mb-6 flex items-center gap-2">
                            <span className="material-symbols-outlined text-sm">security</span> Account Security
                        </h3>

                        <div className="space-y-6">
                            <div className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/10">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 rounded-lg bg-secondary-container/20 flex items-center justify-center text-secondary">
                                        <span className="material-symbols-outlined">verified_user</span>
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-on-surface">
                                            Two-Factor Authentication
                                        </p>
                                        <p className="text-[10px] text-on-surface-variant uppercase tracking-widest">
                                            Not configured
                                        </p>
                                    </div>
                                </div>
                                <button className="text-[10px] uppercase font-bold text-on-surface-variant hover:text-on-surface tracking-widest px-3 py-1.5 bg-surface-container rounded-lg transition-colors">
                                    Configure
                                </button>
                            </div>

                            {/* Password section — hide for OAuth-only users */}
                            {!profile?.oauth_provider && (
                                <div className="space-y-1.5">
                                    <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                                        Update Password
                                    </label>
                                    <div className="relative">
                                        <input
                                            type="password"
                                            id="new_password"
                                            placeholder="Enter new password"
                                            className="w-full bg-surface-container border border-outline-variant/15 text-sm px-4 py-3 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 rounded-lg transition-all"
                                        />
                                        <button
                                            onClick={() => {
                                                const pw = (
                                                    document.getElementById("new_password") as HTMLInputElement
                                                ).value;
                                                if (pw) {
                                                    alert("Password updated successfully!");
                                                    (
                                                        document.getElementById("new_password") as HTMLInputElement
                                                    ).value = "";
                                                }
                                            }}
                                            className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] text-primary font-bold uppercase tracking-widest hover:text-primary-fixed transition-colors"
                                        >
                                            Update
                                        </button>
                                    </div>
                                </div>
                            )}

                            {profile?.oauth_provider && (
                                <div className="p-4 bg-surface-container rounded-lg border border-outline-variant/10 flex items-start gap-3">
                                    <span className="material-symbols-outlined text-primary text-base mt-0.5">
                                        info
                                    </span>
                                    <p className="text-xs text-on-surface-variant leading-relaxed">
                                        Your account is secured via{" "}
                                        <span className="font-bold text-on-surface">{oauthLabel}</span>{" "}
                                        authentication. Password management is handled by your{" "}
                                        {oauthLabel} account.
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="bg-surface-container-low p-6 rounded-lg">
                        <h3 className="text-xs uppercase tracking-[0.2em] text-on-surface-variant font-bold mb-4">
                            Active Sessions
                        </h3>
                        <div className="space-y-2">
                            <div className="flex items-center justify-between p-3 bg-surface-container rounded-lg group border border-outline-variant/5">
                                <div className="flex items-center gap-3">
                                    <span className="material-symbols-outlined text-on-surface-variant">
                                        laptop_mac
                                    </span>
                                    <div>
                                        <p className="text-xs font-medium text-on-surface">
                                            Current Session
                                        </p>
                                        <p className="text-[9px] text-on-surface-variant">
                                            Active now
                                        </p>
                                    </div>
                                </div>
                                <span className="w-2 h-2 rounded-full bg-secondary"></span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* ─── API Management ─── */}
                <section className="col-span-1 lg:col-span-6 bg-surface-container-low p-6 rounded-lg flex flex-col">
                    <div className="flex items-center justify-between mb-8">
                        <h3 className="text-xs uppercase tracking-[0.2em] text-on-surface-variant font-bold flex items-center gap-2">
                            <span className="material-symbols-outlined text-sm">api</span> API Management
                        </h3>
                        <a
                            href="/settings"
                            className="flex items-center gap-2 text-[10px] uppercase font-bold text-primary tracking-widest bg-primary/10 px-3 py-1.5 rounded-lg border border-primary/20 hover:bg-primary/20 transition-colors"
                        >
                            <span className="material-symbols-outlined text-sm">add</span> Manage Keys
                        </a>
                    </div>

                    <div className="space-y-4 flex-1">
                        {profile?.has_binance_key ? (
                            <div className="p-4 bg-surface-container-lowest rounded-lg border border-l-2 border-l-secondary border-outline-variant/10">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-bold text-on-surface">
                                                Binance API Key
                                            </span>
                                            <span className="px-2 py-0.5 bg-secondary-container/20 text-[8px] font-bold text-secondary uppercase rounded">
                                                Active
                                            </span>
                                        </div>
                                        <p className="text-[10px] font-mono text-on-surface-variant mt-2 tracking-wider">
                                            ****************************
                                            {profile.binance_api_key_last4 || "XXXX"}
                                        </p>
                                    </div>
                                    <button
                                        onClick={handleRevokeBinance}
                                        className="p-2 text-on-surface-variant hover:text-tertiary bg-surface-container rounded-lg transition-colors"
                                        title="Revoke Key"
                                    >
                                        <span className="material-symbols-outlined text-sm">delete</span>
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-surface-container-lowest rounded-lg border border-dashed border-outline-variant/20 flex flex-col items-center justify-center text-center py-6">
                                <span className="material-symbols-outlined text-on-surface-variant text-3xl mb-2">
                                    link_off
                                </span>
                                <p className="text-sm font-medium text-on-surface">No Binance connection</p>
                                <a href="/settings" className="text-xs text-primary mt-1 hover:underline">
                                    Connect via Accounts
                                </a>
                            </div>
                        )}

                        {profile?.mt_status && profile.mt_status !== "disconnected" && profile.mt_login ? (
                            <div className="p-4 bg-surface-container-lowest rounded-lg border border-l-2 border-l-primary border-outline-variant/10">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-bold text-on-surface">
                                                MT5 Terminal
                                            </span>
                                            <span
                                                className={`px-2 py-0.5 text-[8px] font-bold uppercase rounded ${
                                                    profile.mt_status === "connected"
                                                        ? "bg-secondary-container/20 text-secondary"
                                                        : "bg-surface-container-highest text-on-surface-variant"
                                                }`}
                                            >
                                                {profile.mt_status}
                                            </span>
                                        </div>
                                        <p className="text-[10px] font-mono text-on-surface-variant mt-2 tracking-wider">
                                            LOGIN: {profile.mt_login} • {profile.mt_server}
                                        </p>
                                    </div>
                                    <button
                                        onClick={handleRevokeMT5}
                                        className="p-2 text-on-surface-variant hover:text-tertiary bg-surface-container rounded-lg transition-colors"
                                        title="Disconnect MT5"
                                    >
                                        <span className="material-symbols-outlined text-sm">delete</span>
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-surface-container-lowest rounded-lg border border-dashed border-outline-variant/20 flex flex-col items-center justify-center text-center py-6">
                                <span className="material-symbols-outlined text-on-surface-variant text-3xl mb-2">
                                    phonelink_off
                                </span>
                                <p className="text-sm font-medium text-on-surface">No MT5 connection</p>
                                <a href="/settings" className="text-xs text-primary mt-1 hover:underline">
                                    Connect via Accounts
                                </a>
                            </div>
                        )}
                    </div>

                    <div className="mt-6 p-4 bg-primary-container/10 rounded-lg border border-primary/20">
                        <div className="flex gap-3">
                            <span className="material-symbols-outlined text-primary">info</span>
                            <div>
                                <p className="text-xs font-semibold text-on-surface">Security Advisory</p>
                                <p className="text-[10px] text-on-surface-variant mt-1 leading-relaxed">
                                    Never share your Secret Keys. DominanceBot will never ask for keys via
                                    email or chat. Keep Withdrawal permissions disabled.
                                </p>
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
}

function Toggle({ active, onClick }: { active: boolean; onClick?: () => void }) {
    return active ? (
        <div
            onClick={onClick}
            className="w-10 h-5 bg-secondary-container rounded-full relative flex items-center px-1 cursor-pointer transition-colors"
        >
            <div className="w-3.5 h-3.5 bg-on-secondary-fixed rounded-full ml-auto shadow-sm"></div>
        </div>
    ) : (
        <div
            onClick={onClick}
            className="w-10 h-5 bg-surface-container-highest rounded-full relative flex items-center px-1 cursor-pointer transition-colors border border-outline-variant/20"
        >
            <div className="w-3.5 h-3.5 bg-on-surface-variant rounded-full shadow-sm"></div>
        </div>
    );
}
