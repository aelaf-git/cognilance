import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/types";
import { Markdown } from "@/components/Markdown";
import { GenUiRenderer } from "@/components/GenUiRenderer";

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

function StreamingCursor() {
  return (
    <span className="ml-0.5 inline-block h-3.5 w-[7px] animate-pulse rounded-[1px] bg-white/70 align-text-bottom" />
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
      <div className="mx-auto max-w-3xl space-y-4 px-3 py-4 sm:space-y-6 sm:px-5 sm:py-6">
        {messages.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-surface/40 px-4 py-8 text-center sm:px-6 sm:py-12">
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
                className={`max-w-[92%] rounded-xl px-3 py-2.5 text-sm leading-relaxed sm:max-w-[85%] sm:px-4 sm:py-3 ${
                  msg.role === "user"
                    ? "bg-registry/15 text-white"
                    : msg.error
                      ? "border border-red-500/30 bg-red-500/10 text-red-300"
                      : "border border-border bg-surface/60 text-white/90"
                }`}
              >
                {msg.streaming && !msg.content ? (
                  <LoadingDots />
                ) : msg.role === "assistant" && !msg.error ? (
                  <div>
                    <Markdown content={msg.content || " "} />
                    {msg.streaming ? <StreamingCursor /> : null}
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content || " "}</p>
                )}
                {msg.role === "assistant" && !msg.streaming && msg.ui?.name ? (
                  <div className="mt-3 border-t border-border pt-3">
                    <GenUiRenderer item={{ name: msg.ui.name, props: msg.ui.props ?? {} }} />
                  </div>
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
