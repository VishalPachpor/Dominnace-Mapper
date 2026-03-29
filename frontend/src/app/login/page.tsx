"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/services/api";
import { useRouter } from "next/navigation";
import Script from "next/script";

declare global {
    interface Window {
        google?: {
            accounts: {
                id: {
                    initialize: (config: Record<string, unknown>) => void;
                    renderButton: (el: HTMLElement, config: Record<string, unknown>) => void;
                    prompt: () => void;
                };
            };
        };
        AppleID?: {
            auth: {
                init: (config: Record<string, unknown>) => void;
                signIn: () => Promise<{ authorization: { id_token: string } }>;
            };
        };
    }
}

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

export default function Login() {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [successMsg, setSuccessMsg] = useState("");
    const [isRegistering, setIsRegistering] = useState(false);
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [googleReady, setGoogleReady] = useState(false);

    // ─── Google One Tap ──────────────────────────────────────────────────────

    const handleGoogleCredential = useCallback(
        async (response: { credential: string }) => {
            setError("");
            setLoading(true);
            try {
                const res = await api.post("/auth/google", {
                    token: response.credential,
                });
                localStorage.setItem("token", res.data.access_token);
                // Refresh token is now set as HttpOnly cookie by the backend
                router.push("/dashboard");
            } catch (err: unknown) {
                const axiosErr = err as { response?: { data?: { detail?: string } } };
                setError(axiosErr.response?.data?.detail || "Google sign-in failed");
            } finally {
                setLoading(false);
            }
        },
        [router]
    );

    useEffect(() => {
        if (!GOOGLE_CLIENT_ID || !googleReady) return;

        window.google?.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: handleGoogleCredential,
            auto_select: false,
            cancel_on_tap_outside: true,
        });

        const btnContainer = document.getElementById("google-btn");
        if (btnContainer) {
            window.google?.accounts.id.renderButton(btnContainer, {
                type: "standard",
                theme: "filled_black",
                size: "large",
                width: "368",
                text: "continue_with",
                shape: "rectangular",
                logo_alignment: "left",
            });
        }
    }, [googleReady, handleGoogleCredential]);

    // ─── Email / Password ────────────────────────────────────────────────────

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setSuccessMsg("");
        setLoading(true);
        try {
            if (isRegistering) {
                await api.post("/auth/register", { email, password });
                setSuccessMsg("Account created! Please sign in.");
                setIsRegistering(false);
            } else {
                const res = await api.post("/auth/login", { email, password });
                localStorage.setItem("token", res.data.access_token);
                // Refresh token is now set as HttpOnly cookie by the backend
                router.push("/dashboard");
            }
        } catch (err: unknown) {
            const axiosErr = err as { response?: { data?: { detail?: string } } };
            setError(
                axiosErr.response?.data?.detail ||
                    (isRegistering ? "Registration failed" : "Login failed")
            );
        } finally {
            setLoading(false);
        }
    };

    // ─── Render ──────────────────────────────────────────────────────────────

    return (
        <>
            {/* Google Identity Services */}
            {GOOGLE_CLIENT_ID && (
                <Script
                    src="https://accounts.google.com/gsi/client"
                    strategy="afterInteractive"
                    onLoad={() => setGoogleReady(true)}
                />
            )}

            <div className="min-h-screen bg-surface flex">
                {/* ─── Left: Branding Panel ─── */}
                <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
                    {/* Gradient background */}
                    <div className="absolute inset-0 bg-gradient-to-br from-primary-container/30 via-surface to-surface-container-low" />

                    {/* Grid pattern overlay */}
                    <div
                        className="absolute inset-0 opacity-[0.03]"
                        style={{
                            backgroundImage:
                                "linear-gradient(var(--color-primary) 1px, transparent 1px), linear-gradient(90deg, var(--color-primary) 1px, transparent 1px)",
                            backgroundSize: "60px 60px",
                        }}
                    />

                    {/* Floating glow orbs */}
                    <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-primary-container/20 rounded-full blur-[120px]" />
                    <div className="absolute bottom-1/3 right-1/4 w-48 h-48 bg-secondary/10 rounded-full blur-[100px]" />

                    {/* Content */}
                    <div className="relative z-10 flex flex-col justify-between p-12 w-full">
                        {/* Top — Logo */}
                        <div>
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center">
                                    <span className="material-symbols-outlined text-on-primary-container text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                                        bolt
                                    </span>
                                </div>
                                <div>
                                    <h1 className="text-on-surface font-bold text-xl tracking-tight">
                                        DominanceBot
                                    </h1>
                                    <p className="text-on-surface-variant text-[10px] uppercase tracking-[0.2em] font-medium">
                                        Trading Platform
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Center — Hero */}
                        <div className="space-y-6">
                            <h2 className="text-4xl xl:text-5xl font-bold text-on-surface leading-tight">
                                Trade smarter
                                <br />
                                with{" "}
                                <span className="text-primary">
                                    dominance
                                </span>{" "}
                                signals.
                            </h2>
                            <p className="text-on-surface-variant text-base leading-relaxed max-w-md">
                                Automated execution powered by proprietary DOM analysis.
                                Forex, metals, and indices — all from one dashboard.
                            </p>

                            {/* Stats row */}
                            <div className="flex gap-8 pt-4">
                                <div>
                                    <p className="text-2xl font-bold text-on-surface">5</p>
                                    <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-medium">
                                        Risk Guards
                                    </p>
                                </div>
                                <div className="border-l border-outline-variant/20 pl-8">
                                    <p className="text-2xl font-bold text-on-surface">&lt;50ms</p>
                                    <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-medium">
                                        Execution
                                    </p>
                                </div>
                                <div className="border-l border-outline-variant/20 pl-8">
                                    <p className="text-2xl font-bold text-on-surface">24/7</p>
                                    <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-medium">
                                        Monitoring
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Bottom — Trust */}
                        <div className="flex items-center gap-2 text-on-surface-variant">
                            <span className="material-symbols-outlined text-base">verified_user</span>
                            <span className="text-xs">Your broker, your funds. We never hold capital.</span>
                        </div>
                    </div>
                </div>

                {/* ─── Right: Auth Panel ─── */}
                <div className="flex-1 flex items-center justify-center p-6 sm:p-8">
                    <div className="w-full max-w-[400px] space-y-8">
                        {/* Mobile logo */}
                        <div className="lg:hidden flex items-center gap-3 justify-center mb-4">
                            <div className="w-9 h-9 rounded-xl bg-primary-container flex items-center justify-center">
                                <span className="material-symbols-outlined text-on-primary-container text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
                                    bolt
                                </span>
                            </div>
                            <h1 className="text-on-surface font-bold text-xl tracking-tight">
                                DominanceBot
                            </h1>
                        </div>

                        {/* Header */}
                        <div className="text-center lg:text-left">
                            <h2 className="text-2xl font-bold text-on-surface">
                                {isRegistering ? "Create your account" : "Welcome back"}
                            </h2>
                            <p className="text-on-surface-variant text-sm mt-1">
                                {isRegistering
                                    ? "Start automating your trades in minutes."
                                    : "Sign in to access your trading dashboard."}
                            </p>
                        </div>

                        {/* Messages */}
                        {error && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-tertiary-container/10 border border-tertiary/20">
                                <span className="material-symbols-outlined text-tertiary text-base">error</span>
                                <p className="text-tertiary text-sm">{error}</p>
                            </div>
                        )}
                        {successMsg && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-secondary-container/10 border border-secondary/20">
                                <span className="material-symbols-outlined text-secondary text-base">check_circle</span>
                                <p className="text-secondary text-sm">{successMsg}</p>
                            </div>
                        )}

                        {/* ─── Social Login ─── */}
                        <div className="space-y-3">
                            {/* Google */}
                            {GOOGLE_CLIENT_ID ? (
                                <div id="google-btn" className="flex justify-center [&>div]:!w-full" />
                            ) : (
                                <button
                                    disabled
                                    className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg border border-outline-variant/20 bg-surface-container text-on-surface-variant text-sm font-medium opacity-40 cursor-not-allowed"
                                >
                                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                                    </svg>
                                    Continue with Google
                                </button>
                            )}
                        </div>

                        {/* Divider */}
                        <div className="flex items-center gap-4">
                            <div className="flex-1 h-px bg-outline-variant/20" />
                            <span className="text-[10px] text-on-surface-variant uppercase tracking-widest font-medium">
                                or continue with email
                            </span>
                            <div className="flex-1 h-px bg-outline-variant/20" />
                        </div>

                        {/* ─── Email Form ─── */}
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Email */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">
                                    Email
                                </label>
                                <div className="relative">
                                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
                                        mail
                                    </span>
                                    <input
                                        type="email"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                        className="w-full pl-10 pr-4 py-3 bg-surface-container border border-outline-variant/20 rounded-lg text-on-surface text-sm placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                                    />
                                </div>
                            </div>

                            {/* Password */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">
                                    Password
                                </label>
                                <div className="relative">
                                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
                                        lock
                                    </span>
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        placeholder={isRegistering ? "Min 8 characters" : "Enter password"}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                        minLength={isRegistering ? 8 : undefined}
                                        className="w-full pl-10 pr-11 py-3 bg-surface-container border border-outline-variant/20 rounded-lg text-on-surface text-sm placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface transition-colors"
                                        tabIndex={-1}
                                    >
                                        <span className="material-symbols-outlined text-lg">
                                            {showPassword ? "visibility_off" : "visibility"}
                                        </span>
                                    </button>
                                </div>
                            </div>

                            {/* Forgot password (login only) */}
                            {!isRegistering && (
                                <div className="flex justify-end">
                                    <button
                                        type="button"
                                        className="text-xs text-primary hover:text-primary-fixed-dim transition-colors"
                                    >
                                        Forgot password?
                                    </button>
                                </div>
                            )}

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full py-3 rounded-lg bg-primary-container text-on-primary-container text-sm font-bold uppercase tracking-wider hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                            >
                                {loading ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                                            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
                                            <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="opacity-75" />
                                        </svg>
                                        Processing...
                                    </>
                                ) : isRegistering ? (
                                    "Create Account"
                                ) : (
                                    "Sign In"
                                )}
                            </button>
                        </form>

                        {/* Toggle register/login */}
                        <p className="text-center text-sm text-on-surface-variant">
                            {isRegistering ? "Already have an account?" : "Don't have an account?"}{" "}
                            <button
                                onClick={() => {
                                    setIsRegistering(!isRegistering);
                                    setError("");
                                    setSuccessMsg("");
                                }}
                                className="text-primary font-medium hover:text-primary-fixed-dim transition-colors"
                            >
                                {isRegistering ? "Sign In" : "Create one"}
                            </button>
                        </p>

                        {/* Footer */}
                        <p className="text-center text-[10px] text-on-surface-variant/50 leading-relaxed">
                            By continuing, you agree to our{" "}
                            <span className="underline cursor-pointer hover:text-on-surface-variant transition-colors">
                                Terms of Service
                            </span>{" "}
                            and{" "}
                            <span className="underline cursor-pointer hover:text-on-surface-variant transition-colors">
                                Privacy Policy
                            </span>
                            .
                        </p>
                    </div>
                </div>
            </div>
        </>
    );
}
