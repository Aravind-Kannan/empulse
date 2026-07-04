import type { ReactNode } from "react";

interface WorkspacePageHeaderProps {
  title: string;
  subtitle: string;
  actions?: ReactNode;
}

export function WorkspacePageHeader({
  title,
  subtitle,
  actions,
}: WorkspacePageHeaderProps) {
  return (
    <div
      className={
        actions
          ? "flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
          : undefined
      }
    >
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-zinc-400">{subtitle}</p>
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
