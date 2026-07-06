import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/types";

function LoadingDots() {
  return (
    <span className="inline-flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </span>
  );
}

export function ChatFeed({
  messages,
  isStreaming,
}: {
  messages: ChatMessage[];
  isStreaming: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin">
      <div className="mx-auto max-w-3xl space-y-6 px-5 py-6">
        {messages.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-surface/40 px-6 py-12 text-center">
            <p className="text-sm font-medium text-white/90">Conversation</p>
            <p className="mt-2 text-sm text-muted">
              Send a message — responses stream here. Open a session card to see planning and
              execution details.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-registry/15 text-white"
                    : msg.error
                      ? "border border-red-500/30 bg-red-500/10 text-red-300"
                      : "border border-border bg-surface/60 text-white/90"
                }`}
              >
                {msg.streaming && !msg.content ? (
                  <LoadingDots />
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content || " "}</p>
                )}
                {msg.streaming && msg.content ? (
                  <span className="mt-2 inline-block">
                    <LoadingDots />
                  </span>
                ) : null}
              </div>
            </div>
          ))
        )}
        {isStreaming && messages[messages.length - 1]?.role !== "assistant" ? (
          <div className="flex justify-start">
            <div className="rounded-xl border border-border bg-surface/60 px-4 py-3">
              <LoadingDots />
            </div>
          </div>
        ) : null}
        <div ref={bottomRef} className="h-1" />
      </div>
    </div>
  );
}
