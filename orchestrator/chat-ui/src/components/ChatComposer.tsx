import { Send, Square } from "lucide-react";
import { useRef, useState } from "react";

export function ChatComposer({
  onSend,
  onStop,
  disabled,
  isStreaming,
}: {
  onSend: (text: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
}) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const value = text.trim();
    if (!value || disabled || isStreaming) return;
    onSend(value);
    setText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  return (
    <div className="shrink-0 border-t border-border bg-surface/80 px-3 py-3 backdrop-blur-sm sm:px-5 sm:py-4">
      <form
        className="mx-auto flex max-w-4xl gap-2 sm:gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          rows={1}
          placeholder={isStreaming ? "Running… tap Stop to cancel" : "Describe what you need…"}
          disabled={disabled || isStreaming}
          className="min-h-[44px] flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-white placeholder:text-dim focus:border-muted focus:outline-none disabled:opacity-50 sm:min-h-[48px] sm:px-4 sm:py-3"
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={() => onStop?.()}
            className="flex h-11 min-w-[44px] shrink-0 items-center justify-center gap-2 rounded-lg border border-red-500/40 bg-red-500/15 px-3 text-sm font-semibold text-red-300 transition-colors hover:bg-red-500/25 sm:h-12 sm:min-w-[88px] sm:px-5"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
            <span className="hidden sm:inline">Stop</span>
          </button>
        ) : (
          <button
            type="submit"
            disabled={disabled || !text.trim()}
            className="flex h-11 min-w-[44px] shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-black transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 sm:h-12 sm:min-w-[88px] sm:px-5"
          >
            <Send className="h-4 w-4" />
            <span className="hidden sm:inline">Send</span>
          </button>
        )}
      </form>
    </div>
  );
}
