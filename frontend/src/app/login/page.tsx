"use client";
import { useState } from "react";
import api from "@/services/api";
import { useRouter } from "next/navigation";

export default function Login() {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [isRegistering, setIsRegistering] = useState(false);
    const [successMsg, setSuccessMsg] = useState("");

    const handleSubmit = async () => {
        setError("");
        setSuccessMsg("");
        try {
            if (isRegistering) {
                await api.post("/auth/register", { email, password });
                setSuccessMsg("Account created! Please sign in.");
                setIsRegistering(false);
            } else {
                const res = await api.post("/auth/login", { email, password });
                localStorage.setItem("token", res.data.access_token);
                router.push("/dashboard");
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || (isRegistering ? "Registration failed" : "Login failed"));
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white">
            <div className="w-full max-w-sm p-8 bg-gray-900 rounded-lg shadow-lg">
                <h2 className="text-2xl font-bold mb-6 text-center text-blue-400">TradingBot Login</h2>

                {error && <p className="text-red-500 mb-4 text-center">{error}</p>}

                {successMsg && <p className="text-green-500 mb-4 text-center">{successMsg}</p>}

                <div className="flex flex-col gap-4">
                    <input
                        className="p-3 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:border-blue-500"
                        placeholder="Email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />

                    <input
                        className="p-3 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:border-blue-500"
                        type="password"
                        placeholder="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                    />

                    <button
                        className="p-3 mt-4 bg-blue-600 hover:bg-blue-700 rounded font-bold transition-colors"
                        onClick={handleSubmit}
                    >
                        {isRegistering ? "Create Account" : "Sign In"}
                    </button>

                    <button
                        className="text-sm text-gray-400 hover:text-white mt-2"
                        onClick={() => {
                            setIsRegistering(!isRegistering);
                            setError("");
                            setSuccessMsg("");
                        }}
                    >
                        {isRegistering ? "Already have an account? Sign In" : "Need an account? Register"}
                    </button>
                </div>
            </div>
        </div>
    );
}
