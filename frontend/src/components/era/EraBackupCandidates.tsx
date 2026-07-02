"use client";

export function EraBackupCandidates() {
  return (
    <section className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/20 p-5">
      <h3 className="text-sm font-medium text-zinc-200">Backup candidates</h3>
      <p className="mt-2 text-sm text-zinc-500">
        No backup candidates identified yet — schedule pairing or connect GitHub
        review data. Ranked backup recommendations ship in Step 10.
      </p>
    </section>
  );
}
