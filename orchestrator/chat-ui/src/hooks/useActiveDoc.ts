import { useCallback, useEffect, useRef, useState } from "react";
import type { ActiveDoc } from "@/types";

const DOC_URL_RE = /docs\.google\.com\/document\/d\/([a-zA-Z0-9_-]+)/i;

function editUrl(documentId: string, url?: string) {
  const base =
    (url && url.trim()) || `https://docs.google.com/document/d/${documentId}/edit`;
  try {
    const u = new URL(base);
    if (!u.searchParams.has("usp")) u.searchParams.set("usp", "sharing");
    if (!u.searchParams.has("rm")) u.searchParams.set("rm", "minimal");
    return u.toString();
  } catch {
    return `https://docs.google.com/document/d/${documentId}/edit?usp=sharing&rm=minimal`;
  }
}

export function parseDocFromText(text: string): ActiveDoc | null {
  const match = DOC_URL_RE.search(text || "");
  if (!match) return null;
  const document_id = match[1];
  return {
    document_id,
    url: editUrl(document_id),
    title: "Google Doc",
  };
}

export function activeDocFromEvent(data: Record<string, unknown>): ActiveDoc | null {
  const document_id = String(data.document_id || "").trim();
  if (!document_id) {
    return parseDocFromText(String(data.document_url || data.url || ""));
  }
  const url = editUrl(document_id, String(data.document_url || data.url || ""));
  const title = String(data.document_title || data.title || "Google Doc").trim() || "Google Doc";
  return { document_id, url, title };
}

function blobFromEvent(data: Record<string, unknown>): string {
  const nested =
    data.data && typeof data.data === "object"
      ? (data.data as Record<string, unknown>)
      : {};
  const parts = [
    data.skill,
    data.tool,
    data.assignee,
    data.title,
    data.document_id,
    data.document_url,
    nested.skill,
    nested.tool,
    JSON.stringify(data.subtasks ?? nested.subtasks ?? ""),
  ];
  return parts.map((p) => String(p || "")).join(" ").toLowerCase();
}

export function isDocsTaskEvent(data: Record<string, unknown>): boolean {
  const event = String(data.event || "");
  if (data.document_id || data.document_url) {
    return event === "subtask_start" || event === "subtask_done" || event === "final";
  }
  const blob = blobFromEvent(data);
  if (
    blob.includes("proposal-writing") ||
    blob.includes("hire:proposal-writing") ||
    blob.includes("docs-creating") ||
    blob.includes("hire:docs-creating") ||
    blob.includes("create_document") ||
    blob.includes("write_document") ||
    blob.includes("batch_update_document")
  ) {
    return true;
  }
  if (event === "plan" || event === "subtask_start") {
    return blob.includes("google-drive") && blob.includes("document");
  }
  return false;
}

export function useActiveDoc(conversationId: string | null | undefined) {
  const [activeDoc, setActiveDoc] = useState<ActiveDoc | null>(null);
  const [open, setOpen] = useState(false);
  const conversationIdRef = useRef(conversationId);
  conversationIdRef.current = conversationId;
  const revisionRef = useRef(0);
  const knownDocRef = useRef<ActiveDoc | null>(null);

  const applyDoc = useCallback((doc: ActiveDoc, opts?: { bumpRevision?: boolean }) => {
    const bumpRevision = Boolean(opts?.bumpRevision);
    if (bumpRevision) {
      revisionRef.current += 1;
    }
    const next: ActiveDoc = {
      ...doc,
      url: editUrl(doc.document_id, doc.url),
      revision: bumpRevision ? revisionRef.current : doc.revision ?? revisionRef.current,
    };
    knownDocRef.current = next;
    setActiveDoc(next);
    return next;
  }, []);

  const pushFromEvent = useCallback(
    (data: Record<string, unknown>) => {
      if (!isDocsTaskEvent(data)) return;
      const event = String(data.event || "");
      const parsed = activeDocFromEvent(data);
      const doc = parsed ?? knownDocRef.current;
      if (!doc) return;
      const bump = event === "final" || event === "subtask_done";
      applyDoc(doc, { bumpRevision: bump });
      setOpen(true);
    },
    [applyDoc],
  );

  const dismiss = useCallback(() => {
    setOpen(false);
  }, []);

  const reopen = useCallback(() => {
    if (knownDocRef.current) {
      setActiveDoc(knownDocRef.current);
      setOpen(true);
    }
  }, []);

  useEffect(() => {
    const cid = conversationId?.trim();
    setOpen(false);
    if (!cid) {
      knownDocRef.current = null;
      setActiveDoc(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/conversations/${cid}/active-doc`);
        if (!res.ok) return;
        const body = (await res.json()) as { active_doc?: ActiveDoc | null };
        if (cancelled) return;
        if (body.active_doc?.document_id) {
          const next = {
            ...body.active_doc,
            url: editUrl(body.active_doc.document_id, body.active_doc.url),
            revision: revisionRef.current,
          };
          knownDocRef.current = next;
          setActiveDoc(next);
        } else {
          knownDocRef.current = null;
          setActiveDoc(null);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  return {
    activeDoc,
    open: Boolean(open && activeDoc),
    pushFromEvent,
    dismiss,
    reopen,
    setOpen,
  };
}
