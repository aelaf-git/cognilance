"use client"

import { Button } from "@/components/ui/button"
import {
  DocxBlock,
  DocxCell,
  DocxDocument,
  DocxRun,
  DocxStyle,
  fontStack
} from "@/lib/docx-document"
import { IconDownload, IconFileText, IconMinus, IconPlus, IconX } from "@tabler/icons-react"
import { CSSProperties, FC, useState } from "react"

interface DocumentPaneProps {
  docx: DocxDocument
  onClose: () => void
}

const HIGHLIGHTS: Record<string, string> = {
  yellow: "#fff3a0",
  green: "#c6efce",
  cyan: "#c6f3f6",
  magenta: "#f7c6e8",
  blue: "#c6d9f7",
  red: "#f8c6c6",
  darkBlue: "#9bb4e0",
  darkYellow: "#e6d48a",
  teal: "#b7e1d8",
  lightGray: "#e5e7eb"
}

const SERIES_COLORS = ["#4f81bd", "#c0504d", "#9bbb59", "#8064a2", "#4bacc6"]
const CALLOUT_FILL: Record<string, string> = {
  note: "#d6e6f5",
  tip: "#d9ead3",
  warning: "#fce4d6"
}

function headingSize(style: DocxStyle, level: number) {
  if (level <= 1) return style.heading_size_pt
  if (level === 2) return Math.max(12, style.heading_size_pt * 0.85)
  return Math.max(12, style.heading_size_pt * 0.75)
}

function previewBlocks(docx: DocxDocument): DocxBlock[] {
  if (docx.blocks.some(block => block.type === "title") || !docx.title) {
    return docx.blocks
  }
  return [{ type: "title", text: docx.title }, ...docx.blocks]
}

function cellValue(cell: DocxCell) {
  return typeof cell === "string" ? { text: cell } : cell
}

function RunText({
  runs,
  text,
  noteNumber
}: {
  runs?: Array<DocxRun & { noteNumber?: number }>
  text?: string
  noteNumber?: number
}) {
  const body = runs?.length
    ? runs.map((run, index) => {
        const style: CSSProperties = {
          fontWeight: run.bold ? 700 : undefined,
          fontStyle: run.italic ? "italic" : undefined,
          textDecoration: run.underline || run.link ? "underline" : undefined,
          color: run.link ? "#0563c1" : run.color ? `#${run.color}` : undefined,
          background: run.highlight ? HIGHLIGHTS[run.highlight] || undefined : undefined
        }
        const content = run.link ? (
          <a href={run.link} style={style}>
            {run.text}
          </a>
        ) : (
          <span style={style}>{run.text}</span>
        )
        return (
          <span key={`run-${index}`}>
            {content}
            {run.noteNumber ? <sup>{run.noteNumber}</sup> : null}
          </span>
        )
      })
    : text
  return (
    <>
      {body}
      {noteNumber ? <sup>{noteNumber}</sup> : null}
    </>
  )
}

function ChartView({ block }: { block: DocxBlock }) {
  const categories = block.categories || []
  const series = block.series || []
  const kind = block.chart || "column"
  const width = 520
  const height = 200
  const pad = 24
  const values = series.flatMap(item => item.values)
  const max = Math.max(1, ...values.map(value => Math.abs(value)))
  const plot = kind === "pie" ? <Pie series={series[0]} /> : null
  const bars =
    kind === "column" || kind === "bar"
      ? categories.map((category, index) => {
          const group = series.map(item => item.values[index] || 0)
          return { category, group }
        })
      : []
  return (
    <figure>
      {block.title ? <figcaption className="mb-1 text-center font-medium">{block.title}</figcaption> : null}
      {plot || (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={categories.join(", ")}>
          {kind === "line" || kind === "area" || kind === "scatter"
            ? series.map((item, seriesIndex) => (
                <SeriesPath
                  key={item.name}
                  values={item.values}
                  categories={categories}
                  color={SERIES_COLORS[seriesIndex % SERIES_COLORS.length]}
                  kind={kind}
                  width={width}
                  height={height}
                  pad={pad}
                  max={max}
                />
              ))
            : bars.map((row, index) =>
                row.group.map((value, seriesIndex) => {
                  const slot = (width - pad * 2) / Math.max(categories.length, 1)
                  const barWidth = Math.max(4, (slot - 8) / Math.max(series.length, 1))
                  const barHeight = (Math.abs(value) / max) * (height - pad * 2)
                  const x = pad + index * slot + 4 + seriesIndex * barWidth
                  if (kind === "bar") {
                    const rowHeight = (height - pad * 2) / Math.max(categories.length, 1)
                    const thickness = Math.max(4, (rowHeight - 8) / Math.max(series.length, 1))
                    const y = pad + index * rowHeight + 4 + seriesIndex * thickness
                    const length = (Math.abs(value) / max) * (width - pad * 2)
                    return (
                      <rect
                        key={`${index}-${seriesIndex}`}
                        x={pad}
                        y={y}
                        width={length}
                        height={thickness}
                        fill={SERIES_COLORS[seriesIndex % SERIES_COLORS.length]}
                      />
                    )
                  }
                  return (
                    <rect
                      key={`${index}-${seriesIndex}`}
                      x={x}
                      y={height - pad - barHeight}
                      width={barWidth}
                      height={barHeight}
                      fill={SERIES_COLORS[seriesIndex % SERIES_COLORS.length]}
                    />
                  )
                })
              )}
        </svg>
      )}
      {kind !== "pie" ? (
        <div className="mt-1 flex justify-between gap-2 text-[9pt] text-neutral-600">
          {categories.map((category, index) => (
            <span key={`${category}-${index}`}>{category}</span>
          ))}
        </div>
      ) : null}
      <div className="mt-1 flex flex-wrap gap-3 text-xs">
        {(kind === "pie" ? categories : series.map(item => item.name)).map((label, index) => (
          <span key={`${label}-${index}`} className="inline-flex items-center gap-1">
            <span
              className="inline-block size-2"
              style={{ background: SERIES_COLORS[index % SERIES_COLORS.length] }}
            />
            {label}
          </span>
        ))}
      </div>
    </figure>
  )
}

function SeriesPath({
  values,
  categories,
  color,
  kind,
  width,
  height,
  pad,
  max
}: {
  values: number[]
  categories: string[]
  color: string
  kind: string
  width: number
  height: number
  pad: number
  max: number
}) {
  const points = values.map((value, index) => {
    const xValue = Number(categories[index])
    const x = Number.isFinite(xValue)
      ? pad + ((xValue - Math.min(...categories.map(item => Number(item) || index))) / Math.max(1, max)) * (width - pad * 2)
      : pad + (index / Math.max(values.length - 1, 1)) * (width - pad * 2)
    const y = height - pad - (Math.abs(value) / max) * (height - pad * 2)
    return `${x},${y}`
  })
  if (kind === "scatter") {
    return (
      <g>
        {points.map(point => {
          const [x, y] = point.split(",")
          return <circle key={point} cx={x} cy={y} r="4" fill={color} />
        })}
      </g>
    )
  }
  if (kind === "area") {
    const first = points[0]?.split(",")[0] || pad
    const last = points[points.length - 1]?.split(",")[0] || width - pad
    return (
      <polygon
        points={`${first},${height - pad} ${points.join(" ")} ${last},${height - pad}`}
        fill={color}
        opacity="0.35"
      />
    )
  }
  return <polyline points={points.join(" ")} fill="none" stroke={color} strokeWidth="2" />
}

function Pie({ series }: { series?: { name: string; values: number[] } }) {
  const values = series?.values || []
  const total = values.reduce((sum, value) => sum + Math.abs(value), 0) || 1
  let cursor = -Math.PI / 2
  return (
    <svg viewBox="0 0 220 180" className="mx-auto w-56" role="img">
      {values.map((value, index) => {
        const sweep = (Math.abs(value) / total) * Math.PI * 2
        const start = cursor
        const end = cursor + sweep
        cursor = end
        const path = arc(110, 86, 70, start, end)
        return <path key={`${series?.name}-${index}`} d={path} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />
      })}
    </svg>
  )
}

function arc(cx: number, cy: number, radius: number, start: number, end: number) {
  const x1 = cx + radius * Math.cos(start)
  const y1 = cy + radius * Math.sin(start)
  const x2 = cx + radius * Math.cos(end)
  const y2 = cy + radius * Math.sin(end)
  const large = end - start > Math.PI ? 1 : 0
  return `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2} Z`
}

function BlockView({
  block,
  style,
  headings,
  blockIndex,
  numbers
}: {
  block: DocxBlock
  style: DocxStyle
  headings: string[]
  blockIndex: number
  numbers: Map<string, number>
}) {
  const after = { marginBottom: `${style.spacing_after_pt}pt` }
  const marker = (key: string) => numbers.get(`${blockIndex}:${key}`)
  const runs = block.runs?.map((run, index) => ({
    ...run,
    noteNumber: marker(`run:${index}`)
  }))
  if (block.type === "title" || block.type === "heading") {
    const level = block.type === "heading" ? block.level || 1 : 0
    const Tag = block.type === "title" ? "h1" : "h2"
    return (
      <Tag
        style={{
          ...after,
          fontFamily: fontStack(style.font_heading),
          fontSize: `${block.type === "title" ? style.title_size_pt : headingSize(style, level)}pt`,
          fontWeight: 700,
          lineHeight: block.type === "title" ? 1.15 : 1.2,
          textAlign: block.type === "heading" && style.alignment === "center" ? "center" : "left"
        }}
      >
        <RunText runs={runs} text={block.text} noteNumber={marker("block")} />
      </Tag>
    )
  }
  if (block.type === "bullet" || block.type === "numbered") {
    const List = block.type === "numbered" ? "ol" : "ul"
    return (
      <List className={block.type === "numbered" ? "list-decimal pl-6" : "list-disc pl-6"} style={after}>
        {(block.items || []).map((item, index) => (
          <li key={`${block.type}-${index}`}>{item}</li>
        ))}
      </List>
    )
  }
  if (block.type === "quote") {
    return (
      <blockquote className="border-l-2 border-neutral-300 pl-3 italic" style={after}>
        <RunText runs={runs} text={block.text} noteNumber={marker("block")} />
        {block.source ? <div className="mt-1 text-right not-italic">{block.source}</div> : null}
      </blockquote>
    )
  }
  if (block.type === "code") {
    return (
      <pre className="overflow-x-auto bg-neutral-100 px-3 py-2 font-mono text-[10pt]" style={after}>
        {block.language ? <div className="mb-1 font-sans text-[9pt] font-semibold">{block.language}</div> : null}
        {block.text}
      </pre>
    )
  }
  if (block.type === "callout") {
    const kind = block.kind || "note"
    return (
      <div className="px-3 py-2" style={{ ...after, background: CALLOUT_FILL[kind] || CALLOUT_FILL.note }}>
        <div className="mb-1 text-[9pt] font-semibold uppercase">{kind}</div>
        <RunText runs={runs} text={block.text} noteNumber={marker("block")} />
      </div>
    )
  }
  if (block.type === "equation") {
    return (
      <p className="text-center" style={{ ...after, fontFamily: fontStack("Cambria Math") }}>
        <RunText runs={runs} text={block.text} noteNumber={marker("block")} />
      </p>
    )
  }
  if (block.type === "rule") {
    return <hr className="my-3 border-neutral-500" />
  }
  if (block.type === "page_break") {
    return (
      <div className="my-4 border-t border-dashed border-neutral-400 py-1 text-center text-[9pt] text-neutral-500">
        Page break
      </div>
    )
  }
  if (block.type === "contents") {
    return (
      <div style={after}>
        <div className="mb-1 font-semibold">Contents</div>
        <ol className="list-decimal pl-6">
          {headings.map((heading, index) => (
            <li key={`contents-${index}`}>{heading}</li>
          ))}
        </ol>
      </div>
    )
  }
  if (block.type === "references") {
    return (
      <div style={after}>
        {(block.items || []).map((item, index) => (
          <p key={`ref-${index}`} style={{ paddingLeft: "0.35in", textIndent: "-0.35in" }}>
            {item}
          </p>
        ))}
      </div>
    )
  }
  if (block.type === "table") {
    return (
      <div style={after}>
        {block.caption ? <p className="italic">{block.caption}</p> : null}
        <table className="w-full border-collapse text-left">
          <tbody>
            {(block.rows || []).map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`}>
                {row.map((cell, cellIndex) => {
                  const header = rowIndex === 0 && block.header !== false
                  const Cell = header ? "th" : "td"
                  const value = cellValue(cell)
                  return (
                    <Cell
                      key={`cell-${rowIndex}-${cellIndex}`}
                      className="border border-neutral-300 px-2 py-1 align-top"
                      style={{ fontWeight: header ? 700 : 400, background: header ? "#d9e2f3" : undefined }}
                    >
                      <RunText
                        runs={value.runs?.map((run, runIndex) => ({
                          ...run,
                          noteNumber: marker(`cell-run:${rowIndex}:${cellIndex}:${runIndex}`)
                        }))}
                        text={value.text}
                        noteNumber={marker(`cell:${rowIndex}:${cellIndex}`)}
                      />
                    </Cell>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (block.type === "chart") {
    return (
      <div style={after}>
        {block.caption ? <p className="italic">{block.caption}</p> : null}
        <ChartView block={block} />
      </div>
    )
  }
  return (
    <p style={{ ...after, whiteSpace: "pre-wrap" }}>
      <RunText runs={runs} text={block.text} noteNumber={marker("block")} />
    </p>
  )
}

function noteNumbers(blocks: DocxBlock[]) {
  const numbers = new Map<string, number>()
  const notes: string[] = []
  const take = (key: string, note?: string) => {
    if (!note) return
    notes.push(note)
    numbers.set(key, notes.length)
  }
  blocks.forEach((block, blockIndex) => {
    block.runs?.forEach((run, index) => take(`${blockIndex}:run:${index}`, run.note))
    take(`${blockIndex}:block`, block.note)
    block.rows?.forEach((row, rowIndex) => {
      row.forEach((cell, cellIndex) => {
        const value = cellValue(cell)
        value.runs?.forEach((run, runIndex) =>
          take(`${blockIndex}:cell-run:${rowIndex}:${cellIndex}:${runIndex}`, run.note)
        )
        take(`${blockIndex}:cell:${rowIndex}:${cellIndex}`, value.note)
      })
    })
  })
  return { numbers, notes }
}

export const DocumentPane: FC<DocumentPaneProps> = ({ docx, onClose }) => {
  const [zoom, setZoom] = useState(100)
  const style = docx.style
  const portraitWidth = style.page === "a4" ? 794 : 816
  const portraitHeight = style.page === "a4" ? 1123 : 1056
  const landscape = style.orientation === "landscape"
  const pageWidth = landscape ? portraitHeight : portraitWidth
  const pageMinHeight = landscape ? portraitWidth : portraitHeight
  const blocks = previewBlocks(docx)
  const headings = blocks
    .filter(block => block.type === "heading" || block.type === "title")
    .map(block => block.text || "")
    .filter(Boolean)
  const { numbers, notes } = noteNumbers(blocks)

  const exportFile = () => {
    const anchor = window.document.createElement("a")
    anchor.href = `/api/docx/${docx.id}`
    anchor.download = `${docx.title || "document"}.docx`
    window.document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-[hsl(var(--chat-canvas))]">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3">
        <IconFileText size={18} className="shrink-0 text-orange-400" />
        <div className="min-w-0 flex-1 truncate text-sm font-medium">{docx.title}</div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label="Zoom out"
            onClick={() => setZoom(current => Math.max(60, current - 10))}
          >
            <IconMinus size={16} />
          </Button>
          <span className="w-10 text-center text-xs tabular-nums text-muted-foreground">{zoom}%</span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label="Zoom in"
            onClick={() => setZoom(current => Math.min(140, current + 10))}
          >
            <IconPlus size={16} />
          </Button>
          <Button type="button" variant="outline" size="sm" className="ml-1 h-8" onClick={exportFile}>
            <IconDownload size={15} className="mr-1.5" />
            Export
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label="Close document"
            onClick={onClose}
          >
            <IconX size={16} />
          </Button>
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-auto px-6 py-8">
        <article
          className="mx-auto flex flex-col bg-white text-neutral-900 shadow-[0_12px_40px_rgba(0,0,0,0.28)]"
          style={{
            zoom: zoom / 100,
            width: pageWidth,
            minHeight: pageMinHeight,
            padding: `${style.margin_inches}in`,
            fontFamily: fontStack(style.font_body),
            fontSize: `${style.body_size_pt}pt`,
            lineHeight: style.line_spacing,
            textAlign: style.alignment === "center" || style.alignment === "justify" ? style.alignment : "left"
          }}
        >
          {style.header ? (
            <div className="mb-4 border-b border-neutral-300 pb-1 text-[10pt]">{style.header}</div>
          ) : null}
          <div
            style={{
              columnCount: style.columns > 1 ? style.columns : undefined,
              columnGap: style.columns > 1 ? "0.5in" : undefined
            }}
          >
            {blocks.map((block, index) => (
              <BlockView
                key={`${docx.id}-${docx.version}-${index}`}
                block={block}
                style={style}
                headings={headings}
                blockIndex={index}
                numbers={numbers}
              />
            ))}
          </div>
          {notes.length ? (
            <ol className="mt-6 list-decimal border-t border-neutral-300 pl-5 pt-2 text-[10pt]">
              {notes.map((note, index) => (
                <li key={`note-${index}`}>{note}</li>
              ))}
            </ol>
          ) : null}
          {style.footer || style.page_numbers ? (
            <div className="mt-auto flex justify-between border-t border-neutral-300 pt-1 text-[10pt]">
              <span>{style.footer}</span>
              {style.page_numbers ? <span>1</span> : null}
            </div>
          ) : null}
        </article>
      </div>
    </div>
  )
}
