import { Send } from "lucide-react";
import { useRef, useState } from "react";

export function ChatComposer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  return (
    <div className="shrink-0 border-t border-border bg-surface/80 px-5 py-4 backdrop-blur-sm">
      <form
        className="mx-auto flex max-w-4xl gap-3"
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
          placeholder="Describe what you need…"
          disabled={disabled}
          className="min-h-[48px] flex-1 resize-none rounded-lg border border-border bg-background px-4 py-3 text-sm text-white placeholder:text-dim focus:border-muted focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="flex h-12 min-w-[88px] items-center justify-center gap-2 rounded-lg bg-white px-5 text-sm font-semibold text-black transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
          Send
        </button>
      </form>
    </div>
  );
}
