"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";

import { streamInvestigationChat } from "@/lib/api";
import type { InvestigationAnalysisStatus } from "@/lib/types";
import type { InvestigationChatMessage } from "@/hooks/useIncidentInvestigation";

import { InvestigationAnalysisProgress } from "./InvestigationAnalysisProgress";

interface InvestigationChatPanelProps {
  incidentId: string | null;
  activeIncidentTitle: string | null;
  suggestions: string[];
  messages: InvestigationChatMessage[];
  onMessagesChange: (messages: InvestigationChatMessage[]) => void;
}

export function InvestigationChatPanel({
  incidentId,
  activeIncidentTitle,
  suggestions,
  messages,
  onMessagesChange,
}: InvestigationChatPanelProps) {
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [analysisStatus, setAnalysisStatus] =
    useState<InvestigationAnalysisStatus | null>(null);
  const streamIdRef = useRef<string | null>(null);
  const assistantContentRef = useRef("");

  useEffect(() => {
    setInput("");
    setStreaming(false);
    setAnalysisStatus(null);
    streamIdRef.current = null;
    assistantContentRef.current = "";
  }, [incidentId]);

  function patchAssistantMessage(
    baseMessages: InvestigationChatMessage[],
    assistantId: string,
    content: string,
  ) {
    return baseMessages.map((msg) =>
      msg.id === assistantId ? { ...msg, content } : msg,
    );
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const userMsg: InvestigationChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const assistantId = `assistant-${Date.now()}`;
    const baseMessages: InvestigationChatMessage[] = [
      ...messages,
      userMsg,
      { id: assistantId, role: "assistant", content: "" },
    ];

    onMessagesChange(baseMessages);
    setInput("");
    setStreaming(true);
    setAnalysisStatus(null);
    streamIdRef.current = assistantId;
    assistantContentRef.current = "";

    try {
      await streamInvestigationChat(
        trimmed,
        incidentId,
        (token) => {
          assistantContentRef.current += token;
          onMessagesChange(
            patchAssistantMessage(
              baseMessages,
              assistantId,
              assistantContentRef.current,
            ),
          );
        },
        (status) => {
          setAnalysisStatus(status);
        },
      );
    } catch (err) {
      onMessagesChange(
        patchAssistantMessage(
          baseMessages,
          assistantId,
          err instanceof Error
            ? `Could not complete analysis: ${err.message}`
            : "Could not complete analysis.",
        ),
      );
    } finally {
      setStreaming(false);
      setAnalysisStatus(null);
      streamIdRef.current = null;
      assistantContentRef.current = "";
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
            {streaming &&
              msg.id === streamIdRef.current &&
              !msg.content &&
              analysisStatus && (
                <InvestigationAnalysisProgress
                  phase={analysisStatus.phase}
                  message={analysisStatus.message}
                />
              )}
            {streaming &&
              msg.id === streamIdRef.current &&
              !msg.content &&
              !analysisStatus && (
                <span className="inline-flex items-center gap-2 text-sm text-zinc-400">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Starting analysis…
                </span>
              )}
            {streaming &&
              msg.id === streamIdRef.current &&
              msg.content && (
                <Loader2 className="mt-1 inline h-3 w-3 animate-spin text-zinc-400" />
              )}
          </div>
        ))}
      </div>

      <div className="border-t border-zinc-800 p-4">
        {suggestions.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {suggestions.map((chip) => (
              <button
                key={chip}
                type="button"
                disabled={streaming || !incidentId}
                onClick={() => sendMessage(chip)}
                className="rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-xs text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100 disabled:opacity-50"
              >
                {chip}
              </button>
            ))}
          </div>
        )}
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
            placeholder={
              activeIncidentTitle
                ? `Ask about ${activeIncidentTitle}…`
                : "Select an incident to ask follow-up questions…"
            }
            disabled={streaming || !incidentId}
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim() || !incidentId}
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
