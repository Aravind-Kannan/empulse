import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <p className="text-sm font-medium uppercase tracking-widest text-zinc-500">
        404
      </p>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-100">
        Page not found
      </h1>
      <p className="mt-3 max-w-md text-base text-zinc-400">
        This route doesn&apos;t exist or may have been moved.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white"
        >
          Go home
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-500"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}
