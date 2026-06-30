"use client";

import { useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";

import { streamInvestigationChat } from "@/lib/api";
import type { InvestigationDiagnostics } from "@/lib/types";

const CHIP_SUGGESTIONS = [
  "Payment Gateway is timing out. Jira: PROJ-992",
  "Auth Service returning 503 errors",
  "Notification Hub retry queue backing up",
  "Escalate to on-call engineer",
  "Check recent deployments for Payment Gateway",
];

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface InvestigationChatPanelProps {
  incidentId: string | null;
  onDiagnostics: (diagnostics: InvestigationDiagnostics) => void;
}

export function InvestigationChatPanel({
  incidentId,
  onDiagnostics,
}: InvestigationChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "I'm connected to the Cognee knowledge graph. Describe the incident or pick a suggestion chip to begin traversal.",
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const streamIdRef = useRef<string | null>(null);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    const assistantId = `assistant-${Date.now()}`;
    streamIdRef.current = assistantId;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "" },
    ]);

    try {
      await streamInvestigationChat(
        trimmed,
        incidentId,
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + token }
                : msg,
            ),
          );
        },
        (diagnostics) => {
          onDiagnostics(diagnostics);
        },
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                content:
                  err instanceof Error
                    ? `Stream failed: ${err.message}`
                    : "Stream failed.",
              }
            : msg,
        ),
      );
    } finally {
      setStreaming(false);
      streamIdRef.current = null;
    }
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-900/30">
      <div className="border-b border-zinc-800 px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Investigation chat
        </h3>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`max-w-[95%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
              msg.role === "user"
                ? "ml-auto bg-sky-600/20 text-sky-100"
                : "bg-zinc-800/80 text-zinc-200"
            }`}
          >
            {msg.content}
            {streaming && msg.id === streamIdRef.current && (
              <Loader2 className="mt-1 inline h-3 w-3 animate-spin text-zinc-400" />
            )}
          </div>
        ))}
      </div>

      <div className="border-t border-zinc-800 p-4">
        <div className="mb-3 flex flex-wrap gap-2">
          {CHIP_SUGGESTIONS.map((chip) => (
            <button
              key={chip}
              type="button"
              disabled={streaming}
              onClick={() => sendMessage(chip)}
              className="rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-xs text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100 disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Payment Gateway is timing out. Jira: PROJ-992"
            disabled={streaming}
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            className="flex items-center justify-center rounded-lg bg-zinc-100 px-3 py-2 text-slate-950 transition hover:bg-white disabled:opacity-50"
          >
            {streaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
