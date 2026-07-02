"use client";

export interface IntegrationSearchItem {
  id: string;
  label: string;
  description?: string;
  badge?: string;
}

interface IntegrationSearchMultiSelectProps {
  items: IntegrationSearchItem[];
  selectedIds: string[];
  onChange: (selectedIds: string[]) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  emptyMessage: string;
  searchPlaceholder?: string;
  inputClassName: string;
}

export function IntegrationSearchMultiSelect({
  items,
  selectedIds,
  onChange,
  searchQuery,
  onSearchChange,
  emptyMessage,
  searchPlaceholder = "Search…",
  inputClassName,
}: IntegrationSearchMultiSelectProps) {
  const selectedSet = new Set(selectedIds);
  const query = searchQuery.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (!query) return true;
    return (
      item.label.toLowerCase().includes(query) ||
      item.id.toLowerCase().includes(query) ||
      (item.description ?? "").toLowerCase().includes(query)
    );
  });

  function toggle(id: string, checked: boolean) {
    if (checked) {
      if (!selectedSet.has(id)) {
        onChange([...selectedIds, id]);
      }
      return;
    }
    onChange(selectedIds.filter((value) => value !== id));
  }

  function selectVisible() {
    const next = new Set(selectedIds);
    for (const item of filtered) {
      next.add(item.id);
    }
    onChange(Array.from(next));
  }

  function clearVisible() {
    const visible = new Set(filtered.map((item) => item.id));
    onChange(selectedIds.filter((id) => !visible.has(id)));
  }

  if (items.length === 0) {
    return (
      <div className="space-y-2">
        {selectedIds.length > 0 && (
          <p className="text-xs text-zinc-400">
            {selectedIds.length} saved selection
            {selectedIds.length === 1 ? "" : "s"} kept: {selectedIds.join(", ")}
          </p>
        )}
        <p className="rounded-lg border border-dashed border-zinc-800 px-3 py-4 text-xs text-zinc-500">
          {emptyMessage}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <input
        type="text"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={searchPlaceholder}
        className={inputClassName}
      />
      <div className="flex items-center justify-between gap-2 text-[11px] text-zinc-500">
        <span>
          {selectedIds.length} selected
          {query ? ` · ${filtered.length} shown` : ""}
        </span>
        <span className="flex gap-2">
          <button
            type="button"
            onClick={selectVisible}
            className="text-sky-400 hover:text-sky-300"
          >
            Select shown
          </button>
          <button
            type="button"
            onClick={clearVisible}
            className="text-zinc-400 hover:text-zinc-300"
          >
            Clear shown
          </button>
        </span>
      </div>
      <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-950 p-2">
        {filtered.length === 0 ? (
          <p className="px-2 py-3 text-xs text-zinc-500">No matches for your search.</p>
        ) : (
          filtered.map((item) => (
            <label
              key={item.id}
              className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-2 hover:bg-zinc-900"
            >
              <input
                type="checkbox"
                checked={selectedSet.has(item.id)}
                onChange={(e) => toggle(item.id, e.target.checked)}
                className="mt-0.5"
              />
              <span className="min-w-0">
                <span className="block text-sm text-zinc-100">
                  {item.label}
                  {item.badge && (
                    <span className="ml-2 text-[10px] uppercase tracking-wide text-zinc-500">
                      {item.badge}
                    </span>
                  )}
                </span>
                {item.description && (
                  <span className="block truncate text-xs text-zinc-500">
                    {item.description}
                  </span>
                )}
              </span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
