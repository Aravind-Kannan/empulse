"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 pl-3 pr-10 text-sm text-zinc-100 outline-none focus:border-zinc-500";

interface SecretInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
}

export function SecretInput({
  value,
  onChange,
  placeholder,
  autoComplete = "one-time-code",
}: SecretInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        spellCheck={false}
        data-1p-ignore
        data-lpignore="true"
        data-form-type="other"
        name="integration-credential"
        className={`${inputClass}${visible ? "" : " secret-input-masked"}`}
      />
      <button
        type="button"
        onClick={() => setVisible((prev) => !prev)}
        aria-label={visible ? "Hide secret" : "Show secret"}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-300"
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
