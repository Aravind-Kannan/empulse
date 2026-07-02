"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send, User, Sparkles } from "lucide-react";

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
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming, analysisStatus]);

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
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-950/20 backdrop-blur-sm shadow-xl">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-zinc-800/80 px-4 py-3.5 bg-zinc-900/10">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
          <Bot className="h-4 w-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">
            Investigation Assistant
          </h3>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
            AI-Powered Assistant
          </p>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-zinc-800">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}
            >
              {/* Avatar */}
              <div
                className={`flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full border text-xs font-semibold ${
                  isUser
                    ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
                    : "border-zinc-700 bg-zinc-800 text-zinc-300"
                }`}
              >
                {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>

              {/* Message Bubble */}
              <div
                className={`group relative max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm transition-all duration-200 ${
                  isUser
                    ? "bg-sky-600/15 border border-sky-500/20 text-sky-100 rounded-tr-none"
                    : "bg-zinc-900/65 border border-zinc-800/90 text-zinc-200 rounded-tl-none"
                }`}
              >
                <div className="whitespace-pre-wrap break-words">
                  {msg.content}
                </div>

                {streaming &&
                  msg.id === streamIdRef.current &&
                  !msg.content &&
                  analysisStatus && (
                    <div className="mt-1 py-1">
                      <InvestigationAnalysisProgress
                        phase={analysisStatus.phase}
                        message={analysisStatus.message}
                      />
                    </div>
                  )}

                {streaming &&
                  msg.id === streamIdRef.current &&
                  !msg.content &&
                  !analysisStatus && (
                    <div className="inline-flex items-center gap-2 py-1 text-zinc-400">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
                      <span className="text-xs animate-pulse">Starting analysis…</span>
                    </div>
                  )}

                {streaming &&
                  msg.id === streamIdRef.current &&
                  msg.content && (
                    <span className="inline-flex ml-1.5 align-middle">
                      <span className="flex h-2 w-2 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
                      </span>
                    </span>
                  )}
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Footer / Input Area */}
      <div className="border-t border-zinc-800/80 p-4 bg-zinc-900/10">
        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="mb-3.5">
            <div className="mb-2 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              <Sparkles className="h-3 w-3 text-sky-400/80" />
              <span>Suggested questions</span>
            </div>
            <div className="flex flex-wrap gap-1.5 max-h-[100px] overflow-y-auto pr-1">
              {suggestions.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  disabled={streaming || !incidentId}
                  onClick={() => sendMessage(chip)}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-2.5 py-1 text-xs text-zinc-300 transition-all duration-150 hover:border-zinc-600 hover:bg-zinc-800/50 hover:text-zinc-100 disabled:opacity-40 disabled:hover:bg-zinc-900/40 disabled:hover:border-zinc-800"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Form */}
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
            className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-sm text-zinc-100 outline-none transition-all duration-150 placeholder:text-zinc-600 focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 disabled:opacity-40"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim() || !incidentId}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-slate-950 transition-all duration-150 hover:bg-white active:scale-95 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:opacity-40 disabled:active:scale-100"
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
