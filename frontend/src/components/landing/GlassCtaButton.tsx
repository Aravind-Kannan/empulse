"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface GlassCtaButtonProps {
  href: string;
  children: React.ReactNode;
}

export function GlassCtaButton({ href, children }: GlassCtaButtonProps) {
  return (
    <Link
      href={href}
      className="group relative inline-flex items-center gap-2 overflow-hidden rounded-2xl px-6 py-3.5 text-sm font-medium text-zinc-100 transition-transform hover:scale-[1.02] active:scale-[0.98]"
    >
      <span className="absolute inset-0 rounded-2xl bg-gradient-to-b from-white/15 to-white/5 backdrop-blur-xl" />
      <span className="absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/20" />
      <span className="landing-cta-glow absolute inset-0 rounded-2xl opacity-0 transition-opacity group-hover:opacity-100" />
      <span className="relative flex items-center gap-2">
        {children}
        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
