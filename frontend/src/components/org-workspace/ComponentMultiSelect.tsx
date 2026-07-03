"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";

import type { Component } from "@/lib/types";

interface ComponentMultiSelectProps {
  components: Component[];
  selectedIds: string[];
  onChange: (componentIds: string[]) => void;
  placeholder?: string;
}

export function ComponentMultiSelect({
  components,
  selectedIds,
  onChange,
  placeholder = "Search components or repository paths…",
}: ComponentMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedComponents = useMemo(
    () => components.filter((component) => selectedIds.includes(component.id)),
    [components, selectedIds],
  );

  const available = useMemo(() => {
    const q = query.trim().toLowerCase();
    return components.filter((component) => {
      if (selectedIds.includes(component.id)) return false;
      if (!q) return true;
      return (
        component.name.toLowerCase().includes(q) ||
        component.description.toLowerCase().includes(q) ||
        component.id.toLowerCase().includes(q)
      );
    });
  }, [components, query, selectedIds]);

  useEffect(() => {
    setHighlightIndex(0);
  }, [query, available.length]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function addComponent(componentId: string) {
    onChange([...selectedIds, componentId]);
    setQuery("");
    setOpen(false);
  }

  function removeComponent(componentId: string) {
    onChange(selectedIds.filter((id) => id !== componentId));
  }

  return (
    <div ref={containerRef} className="space-y-2">
      {selectedComponents.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedComponents.map((component) => (
            <span
              key={component.id}
              className="inline-flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2.5 py-1 text-xs text-sky-100"
            >
              {component.name}
              <button
                type="button"
                onClick={() => removeComponent(component.id)}
                className="rounded-full p-0.5 hover:bg-sky-500/20"
                aria-label={`Remove ${component.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="relative">
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setHighlightIndex((prev) =>
                prev + 1 >= available.length ? 0 : prev + 1,
              );
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setHighlightIndex((prev) =>
                prev - 1 < 0 ? Math.max(available.length - 1, 0) : prev - 1,
              );
            } else if (event.key === "Enter" && open && available.length > 0) {
              event.preventDefault();
              addComponent(available[highlightIndex]?.id ?? available[0]!.id);
            } else if (event.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder={placeholder}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 pr-9 text-sm text-zinc-100 outline-none focus:border-zinc-500"
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setOpen((prev) => !prev)}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-zinc-500 hover:text-zinc-300"
        >
          <ChevronDown className="h-4 w-4" />
        </button>

        {open && available.length > 0 && (
          <ul className="absolute z-50 mt-1 max-h-48 w-full overflow-auto rounded-lg border border-zinc-700 bg-zinc-950 py-1 shadow-xl">
            {available.map((component, index) => (
              <li key={component.id}>
                <button
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => addComponent(component.id)}
                  className={`w-full px-3 py-2 text-left text-sm ${
                    index === highlightIndex
                      ? "bg-zinc-800 text-zinc-100"
                      : "text-zinc-300 hover:bg-zinc-900"
                  }`}
                >
                  <p className="font-medium">{component.name}</p>
                  {component.description && (
                    <p className="truncate text-xs text-zinc-500">
                      {component.description}
                    </p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-zinc-500">
        {components.length === 0
          ? "No components yet — sync GitHub or Jira integrations to auto-discover components, or assign ownership later in settings."
          : "Link to any number of architectural assets. Contribution % is computed dynamically by Cognee at ERA refresh."}
      </p>
    </div>
  );
}
