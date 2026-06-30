"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

interface RoleComboboxProps {
  value: string;
  suggestions: string[];
  onChange: (value: string) => void;
  placeholder?: string;
}

const CREATE_PREFIX = 'Create new role: "';

function isCreateOption(option: string): boolean {
  return option.startsWith(CREATE_PREFIX);
}

function createOptionLabel(role: string): string {
  return `${CREATE_PREFIX}${role}"`;
}

export function RoleCombobox({
  value,
  suggestions,
  onChange,
  placeholder = "e.g. Senior Platform Engineer",
}: RoleComboboxProps) {
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const query = value.trim().toLowerCase();
    if (!query) return suggestions;
    return suggestions.filter((role) => role.toLowerCase().includes(query));
  }, [value, suggestions]);

  const trimmedValue = value.trim();
  const showCreateOption =
    trimmedValue.length > 0 &&
    !suggestions.some(
      (role) => role.toLowerCase() === trimmedValue.toLowerCase(),
    );

  const options = showCreateOption
    ? [createOptionLabel(trimmedValue), ...filtered]
    : filtered;

  useEffect(() => {
    setHighlightIndex(0);
  }, [value, filtered.length, showCreateOption]);

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

  function selectOption(option: string) {
    if (isCreateOption(option)) {
      onChange(trimmedValue);
    } else {
      onChange(option);
    }
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <input
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
              setOpen(true);
              return;
            }
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setHighlightIndex((prev) =>
                prev + 1 >= options.length ? 0 : prev + 1,
              );
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setHighlightIndex((prev) =>
                prev - 1 < 0 ? Math.max(options.length - 1, 0) : prev - 1,
              );
            } else if (event.key === "Enter" && open && options.length > 0) {
              event.preventDefault();
              selectOption(options[highlightIndex] ?? options[0]!);
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
      </div>

      {open && options.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-48 w-full overflow-auto rounded-lg border border-zinc-700 bg-zinc-950 py-1 shadow-xl">
          {options.map((option, index) => (
            <li key={`${option}-${index}`}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(option)}
                className={`w-full px-3 py-2 text-left text-sm ${
                  index === highlightIndex
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-300 hover:bg-zinc-900"
                } ${isCreateOption(option) ? "text-emerald-300" : ""}`}
              >
                {option}
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && options.length === 0 && trimmedValue && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-400 shadow-xl">
          Press Enter to use &ldquo;{trimmedValue}&rdquo;
        </div>
      )}
    </div>
  );
}
