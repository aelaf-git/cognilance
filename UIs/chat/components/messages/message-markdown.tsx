import { prepareAnswer } from "@/lib/prepare-answer"
import "katex/dist/katex.min.css"
import React, { FC } from "react"
import rehypeKatex from "rehype-katex"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import { MessageCodeBlock } from "./message-codeblock"
import { MessageMarkdownMemoized } from "./message-markdown-memoized"

interface MessageMarkdownProps {
  content: string
}

export const MessageMarkdown: FC<MessageMarkdownProps> = ({ content }) => {
  return (
    <MessageMarkdownMemoized
      className="prose prose-sm dark:prose-invert prose-headings:font-[family-name:var(--font-display)] prose-headings:font-semibold prose-headings:tracking-tight prose-p:leading-7 prose-a:text-primary prose-a:no-underline hover:prose-a:underline prose-pre:my-4 prose-pre:rounded-xl prose-pre:border prose-pre:border-border/60 prose-pre:p-0 prose-table:my-4 prose-table:overflow-hidden prose-table:rounded-lg prose-th:bg-muted/70 prose-th:px-3 prose-td:px-3 prose-img:rounded-xl prose-img:border prose-img:border-border/60 prose-ol:my-3 prose-ul:my-3 prose-li:my-1 prose-blockquote:my-3 prose-blockquote:border-border min-w-full max-w-none break-words [&_.katex-display]:my-3 [&_.katex-display]:overflow-x-auto [&_.katex-display]:overflow-y-hidden"
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[[rehypeKatex, { throwOnError: false }]]}
      components={{
        p({ children }) {
          return <p className="mb-3 last:mb-0">{children}</p>
        },
        ol({ children, start }) {
          return (
            <ol start={start} className="my-3 list-decimal space-y-2 pl-5">
              {children}
            </ol>
          )
        },
        ul({ children }) {
          return <ul className="my-3 list-disc space-y-1 pl-5">{children}</ul>
        },
        li({ children }) {
          return <li className="leading-7">{children}</li>
        },
        blockquote({ children }) {
          return (
            <blockquote className="my-3 border-l-2 border-border pl-3 text-muted-foreground">
              {children}
            </blockquote>
          )
        },
        img({ node, ...props }) {
          return <img className="max-w-full sm:max-w-[80%]" {...props} />
        },
        code({ node, className, children, ...props }) {
          const childArray = React.Children.toArray(children)
          const firstChild = childArray[0] as React.ReactElement
          const firstChildAsString = React.isValidElement(firstChild)
            ? (firstChild as React.ReactElement).props.children
            : firstChild

          if (firstChildAsString === "▍") {
            return <span className="mt-1 animate-pulse cursor-default">▍</span>
          }

          if (typeof firstChildAsString === "string") {
            childArray[0] = firstChildAsString.replace("`▍`", "▍")
          }

          const match = /language-(\w+)/.exec(className || "")

          if (
            typeof firstChildAsString === "string" &&
            !firstChildAsString.includes("\n")
          ) {
            return (
              <code className={className} {...props}>
                {childArray}
              </code>
            )
          }

          return (
            <MessageCodeBlock
              key={Math.random()}
              language={(match && match[1]) || ""}
              value={String(childArray).replace(/\n$/, "")}
              {...props}
            />
          )
        }
      }}
    >
      {prepareAnswer(content)}
    </MessageMarkdownMemoized>
  )
}
