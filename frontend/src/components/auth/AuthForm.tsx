"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { useAuthErrorFromUrl } from "@/hooks/useAuthErrorFromUrl";
import { oauthLoginUrl } from "@/lib/auth";
import {
  getAuthUnavailableMessage,
  isAuthServiceUnavailable,
} from "@/lib/connectivity";
import { isBackendWarmupActive } from "@/lib/backend-warmup-state";

const INPUT_CLASS =
  "w-full rounded-xl border border-zinc-700/80 bg-black/40 px-4 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20";

interface AuthFormProps {
  mode: "login" | "signup";
}

export function AuthForm({ mode }: AuthFormProps) {
  const { login, signUp } = useAuth();
  const oauthError = useAuthErrorFromUrl();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [company, setCompany] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formNotice, setFormNotice] = useState<string | null>(null);
  const [oauthDismissed, setOauthDismissed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const isSignup = mode === "signup";
  const oauthNextPath = isSignup ? "/onboarding" : "/dashboard";

  const displayError =
    formError ?? (!oauthDismissed && oauthError ? oauthError : null);

  useEffect(() => {
    if (oauthError) {
      setOauthDismissed(false);
    }
  }, [oauthError]);

  function dismissOAuthError() {
    if (oauthError && !oauthDismissed) {
      setOauthDismissed(true);
    }
  }

  function clearMessages() {
    setFormError(null);
    setFormNotice(null);
  }

  function handleGoogleSignIn() {
    clearMessages();
    setOauthDismissed(true);
    window.location.href = oauthLoginUrl("google", oauthNextPath);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    dismissOAuthError();
    clearMessages();

    if (!email.trim()) {
      setFormError("Email is required.");
      return;
    }
    if (!password.trim()) {
      setFormError("Password is required.");
      return;
    }
    if (password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isBackendWarmupActive()) {
        setFormNotice(getAuthUnavailableMessage(true));
        return;
      }

      if (isSignup) {
        if (!name.trim()) {
          setFormError("Name is required.");
          return;
        }
        if (!company.trim()) {
          setFormError("Company name is required.");
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
      if (isAuthServiceUnavailable(err)) {
        setFormNotice(getAuthUnavailableMessage(isBackendWarmupActive()));
      } else {
        setFormError(
          err instanceof Error ? err.message : "Authentication failed.",
        );
      }
    } finally {
      setSubmitting(false);
    }
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

      {formNotice ? (
        <p className="mb-4 rounded-lg border border-zinc-700/70 bg-zinc-900/50 px-3 py-2.5 text-sm leading-relaxed text-zinc-300">
          {formNotice}
        </p>
      ) : null}

      {displayError ? (
        <p className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {displayError}
        </p>
      ) : null}

      <div className="mb-6 space-y-2.5">
        <button
          type="button"
          onClick={handleGoogleSignIn}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-700/80 bg-black/30 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-600 hover:bg-black/50"
        >
          <GoogleIcon />
          Continue with Google
        </button>
        <div className="relative py-2">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <div className="relative flex justify-center text-[10px] uppercase tracking-widest">
            <span className="bg-transparent px-3 text-zinc-600">or</span>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {isSignup && (
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              Full name
            </label>
            <input
              value={name}
              onChange={(event) => {
                dismissOAuthError();
                setName(event.target.value);
                clearMessages();
              }}
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
            onChange={(event) => {
              dismissOAuthError();
              setEmail(event.target.value);
              clearMessages();
            }}
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
            onChange={(event) => {
              dismissOAuthError();
              setPassword(event.target.value);
              clearMessages();
            }}
            placeholder={isSignup ? "At least 8 characters" : "Your password"}
            autoComplete={isSignup ? "new-password" : "current-password"}
            className={INPUT_CLASS}
          />
        </div>

        {isSignup ? (
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              Company
            </label>
            <input
              value={company}
              onChange={(event) => {
                dismissOAuthError();
                setCompany(event.target.value);
                clearMessages();
              }}
              placeholder="Acme Corp"
              autoComplete="organization"
              className={INPUT_CLASS}
            />
          </div>
        ) : null}

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
