"use client";

import { useState } from "react";
import { X } from "lucide-react";

import { useAuth } from "@/context/AuthContext";

type AuthMode = "login" | "signup";

interface AuthModalProps {
  mode: AuthMode;
  onClose: () => void;
  onSwitchMode: (mode: AuthMode) => void;
}

export function AuthModal({ mode, onClose, onSwitchMode }: AuthModalProps) {
  const { login, signUp } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("Acme Company");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    if (mode === "signup") {
      if (!name.trim()) {
        setError("Name is required for sign up.");
        return;
      }
      signUp({ name: name.trim(), email: email.trim(), company: company.trim() });
      return;
    }

    login({ email: email.trim(), name: name.trim() || undefined });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close auth modal"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md rounded-2xl border border-zinc-800 bg-slate-950 p-6 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              {mode === "signup" ? "New manager" : "Returning manager"}
            </p>
            <h2 className="text-xl font-semibold text-zinc-100">
              {mode === "signup" ? "Create your workspace" : "Welcome back"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-5 flex rounded-lg border border-zinc-800 bg-zinc-900/50 p-1">
          <button
            type="button"
            onClick={() => onSwitchMode("login")}
            className={`flex-1 rounded-md px-3 py-2 text-sm transition ${
              mode === "login"
                ? "bg-zinc-100 text-slate-950"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => onSwitchMode("signup")}
            className={`flex-1 rounded-md px-3 py-2 text-sm transition ${
              mode === "signup"
                ? "bg-zinc-100 text-slate-950"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="mb-1.5 block text-sm text-zinc-400">
                Full name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Alice Chen"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
          )}
          <div>
            <label className="mb-1.5 block text-sm text-zinc-400">
              Work email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alice@acme.com"
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
            />
          </div>
          {mode === "signup" && (
            <div>
              <label className="mb-1.5 block text-sm text-zinc-400">
                Company
              </label>
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
          )}
          {mode === "login" && (
            <div>
              <label className="mb-1.5 block text-sm text-zinc-400">
                Name (optional)
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Alice Chen"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </div>
          )}

          {error && <p className="text-sm text-red-300">{error}</p>}

          <button
            type="submit"
            className="w-full rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white"
          >
            {mode === "signup" ? "Continue to onboarding" : "Login to dashboard"}
          </button>
        </form>
      </div>
    </div>
  );
}
