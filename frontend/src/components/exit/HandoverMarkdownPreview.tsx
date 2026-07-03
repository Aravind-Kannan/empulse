"use client";

import type { ReactNode } from "react";

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={`${match.index}-b`} className="font-semibold text-zinc-100">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("`")) {
      nodes.push(
        <code
          key={`${match.index}-c`}
          className="rounded bg-zinc-800/80 px-1.5 py-0.5 font-mono text-xs text-sky-200"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (linkMatch) {
        nodes.push(
          <a
            key={`${match.index}-a`}
            href={linkMatch[2]}
            target="_blank"
            rel="noreferrer"
            className="text-sky-400 underline decoration-sky-500/40 underline-offset-2 hover:text-sky-300"
          >
            {linkMatch[1]}
          </a>,
        );
      }
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : [text];
}

interface HandoverMarkdownPreviewProps {
  markdown: string;
}

export function HandoverMarkdownPreview({ markdown }: HandoverMarkdownPreviewProps) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let listItems: ReactNode[] = [];
  let key = 0;

  function flushList() {
    if (listItems.length === 0) return;
    blocks.push(
      <ul key={`list-${key++}`} className="my-3 list-disc space-y-1.5 pl-5 text-zinc-300">
        {listItems}
      </ul>,
    );
    listItems = [];
  }

  for (const line of lines) {
    const trimmed = line.trimEnd();

    if (trimmed.startsWith("# ")) {
      flushList();
      blocks.push(
        <h1 key={`h1-${key++}`} className="mb-4 text-2xl font-semibold tracking-tight text-zinc-50">
          {renderInline(trimmed.slice(2))}
        </h1>,
      );
      continue;
    }

    if (trimmed.startsWith("## ")) {
      flushList();
      blocks.push(
        <h2
          key={`h2-${key++}`}
          className="mb-3 mt-8 border-b border-zinc-800 pb-2 text-lg font-semibold text-zinc-100"
        >
          {renderInline(trimmed.slice(3))}
        </h2>,
      );
      continue;
    }

    if (trimmed.startsWith("### ")) {
      flushList();
      blocks.push(
        <h3 key={`h3-${key++}`} className="mb-2 mt-5 text-base font-medium text-zinc-200">
          {renderInline(trimmed.slice(4))}
        </h3>,
      );
      continue;
    }

    if (trimmed.startsWith("> ")) {
      flushList();
      blocks.push(
        <blockquote
          key={`q-${key++}`}
          className="my-3 border-l-2 border-violet-500/50 bg-violet-500/5 px-4 py-2 text-sm italic text-zinc-400"
        >
          {renderInline(trimmed.slice(2))}
        </blockquote>,
      );
      continue;
    }

    if (trimmed.startsWith("- ")) {
      listItems.push(
        <li key={`li-${key++}`} className="leading-relaxed">
          {renderInline(trimmed.slice(2))}
        </li>,
      );
      continue;
    }

    if (trimmed === "") {
      flushList();
      continue;
    }

    flushList();
    blocks.push(
      <p key={`p-${key++}`} className="my-2 leading-relaxed text-zinc-300">
        {renderInline(trimmed)}
      </p>,
    );
  }

  flushList();

  return <article className="handover-markdown-preview">{blocks}</article>;
}
