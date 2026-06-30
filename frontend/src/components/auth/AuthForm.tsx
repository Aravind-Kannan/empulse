"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { fetchAuthProviders, oauthLoginUrl } from "@/lib/auth";

const INPUT_CLASS =
  "w-full rounded-xl border border-zinc-700/80 bg-black/40 px-4 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20";

interface AuthFormProps {
  mode: "login" | "signup";
}

export function AuthForm({ mode }: AuthFormProps) {
  const { login, signUp } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [company, setCompany] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [providers, setProviders] = useState<{
    google: boolean;
    github: boolean;
  } | null>(null);

  const isSignup = mode === "signup";
  const showGoogle = providers?.google ?? false;
  const showGithub = providers?.github ?? false;
  const showOAuth = showGoogle || showGithub;

  useEffect(() => {
    fetchAuthProviders()
      .then(setProviders)
      .catch(() => setProviders({ google: false, github: false }));
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    if (!password.trim()) {
      setError("Password is required.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        if (!name.trim()) {
          setError("Name is required.");
          return;
        }
        if (!company.trim()) {
          setError("Company name is required.");
          return;
        }
        await signUp({
          name: name.trim(),
          email: email.trim(),
          password,
          company: company.trim(),
        });
        return;
      }
      await login({ email: email.trim(), password });
    } catch (err) {
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        setError(
          "Cannot reach the API server. Ensure the backend is running on port 8000.",
        );
      } else {
        setError(err instanceof Error ? err.message : "Authentication failed.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleOAuth(provider: "google" | "github") {
    const nextPath = isSignup ? "/onboarding" : "/dashboard";
    window.location.href = oauthLoginUrl(provider, nextPath);
  }

  return (
    <>
      <div className="mb-8">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">
          {isSignup ? "Create account" : "Sign in"}
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
          {isSignup ? "Start your workspace" : "Welcome back"}
        </h2>
        <p className="mt-2 text-sm text-zinc-500">
          {isSignup
            ? "Set up your tenant and begin onboarding."
            : "Access your engineering intelligence cockpit."}
        </p>
      </div>

      {showOAuth && (
        <div className="mb-6 space-y-2.5">
          {showGoogle && (
            <button
              type="button"
              onClick={() => handleOAuth("google")}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-700/80 bg-black/30 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-600 hover:bg-black/50"
            >
              <GoogleIcon />
              Continue with Google
            </button>
          )}
          {showGithub && (
            <button
              type="button"
              onClick={() => handleOAuth("github")}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-700/80 bg-black/30 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-600 hover:bg-black/50"
            >
              <GitHubIcon />
              Continue with GitHub
            </button>
          )}
          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-zinc-800" />
            </div>
            <div className="relative flex justify-center text-[10px] uppercase tracking-widest">
              <span className="bg-transparent px-3 text-zinc-600">or</span>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {isSignup && (
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              Full name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Alice Chen"
              autoComplete="name"
              className={INPUT_CLASS}
            />
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-xs font-medium text-zinc-400">
            Work email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="alice@acme.com"
            autoComplete="email"
            className={INPUT_CLASS}
          />
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium text-zinc-400">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={isSignup ? "At least 8 characters" : "Your password"}
            autoComplete={isSignup ? "new-password" : "current-password"}
            className={INPUT_CLASS}
          />
        </div>

        {isSignup && (
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              Company
            </label>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Acme Corp"
              autoComplete="organization"
              className={INPUT_CLASS}
            />
          </div>
        )}

        {error && (
          <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-zinc-100 px-4 py-3 text-sm font-medium text-black transition hover:bg-white disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isSignup ? "Create workspace" : "Sign in to dashboard"}
        </button>
      </form>

      <p className="mt-8 text-center text-sm text-zinc-500">
        {isSignup ? (
          <>
            Already have an enterprise space?{" "}
            <Link
              href="/login"
              className="font-medium text-zinc-300 underline-offset-4 hover:text-white hover:underline"
            >
              Log in
            </Link>
          </>
        ) : (
          <>
            New here?{" "}
            <Link
              href="/signup"
              className="font-medium text-zinc-300 underline-offset-4 hover:text-white hover:underline"
            >
              Create an account
            </Link>
          </>
        )}
      </p>
    </>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M12 10.2v3.6h5.1c-.2 1.2-1.6 3.5-5.1 3.5-3.1 0-5.6-2.5-5.6-5.6S8.9 6.1 12 6.1c1.8 0 3 .8 3.7 1.5l2.5-2.4C16.8 3.7 14.6 2.7 12 2.7 6.9 2.7 2.7 6.9 2.7 12s4.2 9.3 9.3 9.3c5.4 0 9-3.8 9-9.1 0-.6-.1-1.1-.2-1.5H12z"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.395-.135-.345-.72-1.395-1.23-1.875-.42-.45-1.02-.78 0-.795 1.005-.015 1.725.93 1.965 1.315 1.155 1.935 3.015 1.395 3.75 1.065.105-.825.435-1.395.795-1.715-2.775-.315-5.685-1.395-5.685-6.21 0-1.365.495-2.475 1.305-3.345-.135-.315-.57-1.605.135-3.33 0 0 1.065-.33 3.495 1.275 1.005-.285 2.085-.42 3.165-.42 1.08 0 2.16.135 3.165.42 2.43-1.62 3.495-1.275 3.495-1.275.705 1.725.27 3.015.135 3.33.81.87 1.305 1.98 1.305 3.345 0 4.83-2.925 5.895-5.7 6.21.435.375.81 1.095.81 2.205 0 1.59-.015 2.865-.015 3.255 0 .315.225.69.825.57A9.02 9.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}
