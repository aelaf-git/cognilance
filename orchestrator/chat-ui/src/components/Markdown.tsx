import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const HTML_HINT_RE = /<(div|p|br|span|a|ul|ol|li|h[1-6]|strong|em|b|i|u|table|tr|td)[\s>/]/i;
const TAG_RE = /<\/?[a-z][^>]*>/gi;

/** Safety net: models occasionally leak raw HTML (e.g. email bodies) into answers. */
export function sanitizeAnswer(text: string): string {
  if (!HTML_HINT_RE.test(text)) return text;
  return text
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|h[1-6]|li|tr)>/gi, "\n")
    .replace(TAG_RE, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown-body space-y-2 text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          h1: ({ children }) => (
            <h1 className="mt-3 text-base font-semibold text-white first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-3 text-base font-semibold text-white first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-2 text-sm font-semibold text-white first:mt-0">{children}</h3>
          ),
          p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-registry underline decoration-registry/40 underline-offset-2 hover:decoration-registry"
            >
              {children}
            </a>
          ),
          ul: ({ children }) => <ul className="ml-4 list-disc space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="ml-4 list-decimal space-y-1">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-border pl-3 text-muted">{children}</blockquote>
          ),
          code: ({ className, children }) => {
            const isBlock = /language-/.test(className ?? "") || String(children).includes("\n");
            if (isBlock) {
              return (
                <code className="block overflow-x-auto rounded-md border border-border bg-black/40 p-3 font-mono text-xs">
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs">{children}</code>
            );
          },
          pre: ({ children }) => <pre className="my-1">{children}</pre>,
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-border bg-white/5 px-2 py-1.5 text-left font-medium text-white">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border px-2 py-1.5 align-top">{children}</td>
          ),
          hr: () => <hr className="border-border" />,
        }}
      >
        {sanitizeAnswer(content)}
      </ReactMarkdown>
    </div>
  );
}
