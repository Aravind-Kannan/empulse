"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface GlassCtaButtonProps {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "secondary";
}

export function GlassCtaButton({
  href,
  children,
  variant = "primary",
}: GlassCtaButtonProps) {
  const isPrimary = variant === "primary";

  return (
    <Link
      href={href}
      className={`group relative inline-flex items-center gap-2 overflow-hidden rounded-2xl px-6 py-3.5 text-sm font-medium transition-transform hover:scale-[1.02] active:scale-[0.98] ${
        isPrimary ? "text-zinc-100" : "text-zinc-300"
      }`}
    >
      <span
        className={`absolute inset-0 rounded-2xl backdrop-blur-xl ${
          isPrimary
            ? "bg-gradient-to-b from-white/15 to-white/5"
            : "bg-slate-900/40"
        }`}
      />
      <span
        className={`absolute inset-0 rounded-2xl ring-1 ring-inset ${
          isPrimary ? "ring-white/20" : "ring-zinc-700/80"
        }`}
      />
      {isPrimary ? (
        <span className="landing-cta-glow absolute inset-0 rounded-2xl opacity-0 transition-opacity group-hover:opacity-100" />
      ) : null}
      <span className="relative flex items-center gap-2">
        {children}
        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
