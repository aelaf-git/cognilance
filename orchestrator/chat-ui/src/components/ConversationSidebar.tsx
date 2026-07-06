import type { ConversationSummary } from "@/types";

export function ConversationSidebarCollapsed({ onExpand }: { onExpand: () => void }) {
  return (
    <div className="flex h-full w-10 shrink-0 flex-col border-r border-border bg-background">
      <button
        type="button"
        onClick={onExpand}
        title="Show conversations"
        className="flex h-12 w-full items-center justify-center text-muted hover:bg-surface hover:text-white"
      >
        <MenuIcon />
      </button>
    </div>
  );
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onCollapse,
  onSelect,
  onDelete,
  onNewChat,
  newChatDisabled,
}: {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onCollapse: () => void;
  onSelect: (conversationId: string) => void;
  onDelete: (conversationId: string) => void;
  onNewChat: () => void;
  newChatDisabled?: boolean;
}) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2.5">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
          Conversations
        </h3>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewChat}
            disabled={newChatDisabled}
            title="New chat"
            className="rounded p-1.5 text-dim hover:bg-surface hover:text-white disabled:opacity-50"
          >
            <PlusIcon />
          </button>
          <button
            type="button"
            onClick={onCollapse}
            title="Hide conversations"
            className="rounded p-1.5 text-dim hover:bg-surface hover:text-white"
          >
            <MenuIcon />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3 scrollbar-thin">
        {conversations.length === 0 ? (
          <p className="text-xs text-dim">No conversations yet.</p>
        ) : (
          conversations.map((conversation) => {
            const active = activeConversationId === conversation.id;
            return (
              <div
                key={conversation.id}
                className={`rounded-lg border transition-colors ${
                  active
                    ? "border-registry/40 bg-registry/10"
                    : "border-border bg-surface/60 hover:border-border/80"
                }`}
              >
                <div className="flex items-start gap-1">
                  <button
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                    className="min-w-0 flex-1 px-2.5 py-2 text-left"
                  >
                    <p className="truncate text-xs text-white">{conversation.title}</p>
                    <p className="mt-1 text-[10px] text-dim">
                      {(conversation.session_count ?? 0) === 0
                        ? "No sessions"
                        : `${conversation.session_count} session${(conversation.session_count ?? 0) === 1 ? "" : "s"}`}
                    </p>
                  </button>
                  <button
                    type="button"
                    title="Delete conversation"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (
                        window.confirm(
                          "Delete this conversation and all its sessions? This cannot be undone.",
                        )
                      ) {
                        onDelete(conversation.id);
                      }
                    }}
                    className="mr-2 mt-2 shrink-0 rounded p-1 text-dim hover:bg-red-500/10 hover:text-red-400"
                  >
                    <TrashIcon />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </svg>
  );
}
