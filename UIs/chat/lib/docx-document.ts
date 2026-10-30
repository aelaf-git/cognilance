export type DocxRun = {
  text: string
  bold?: boolean
  italic?: boolean
  underline?: boolean
  color?: string
  highlight?: string
  link?: string
  note?: string
}

export type DocxCell =
  | string
  | {
      text?: string
      runs?: DocxRun[]
      note?: string
    }

export type DocxSeries = {
  name: string
  values: number[]
}

export type DocxBlock = {
  type:
    | "title"
    | "heading"
    | "paragraph"
    | "bullet"
    | "numbered"
    | "table"
    | "quote"
    | "code"
    | "callout"
    | "equation"
    | "rule"
    | "page_break"
    | "chart"
    | "contents"
    | "references"
  text?: string
  level?: number
  items?: string[]
  rows?: DocxCell[][]
  header?: boolean
  caption?: string
  runs?: DocxRun[]
  note?: string
  source?: string
  language?: string
  kind?: string
  chart?: string
  title?: string
  categories?: string[]
  series?: DocxSeries[]
}

export type DocxStyle = {
  font_body: string
  font_heading: string
  body_size_pt: number
  heading_size_pt: number
  title_size_pt: number
  alignment: string
  margin_inches: number
  page: string
  spacing_after_pt: number
  line_spacing: number
  header: string
  footer: string
  page_numbers: boolean
  orientation: "portrait" | "landscape"
  columns: number
}

export type DocxDocument = {
  id: string
  title: string
  version: number
  style: DocxStyle
  blocks: DocxBlock[]
}

export const DEFAULT_DOCX_STYLE: DocxStyle = {
  font_body: "Calibri",
  font_heading: "Calibri",
  body_size_pt: 11,
  heading_size_pt: 16,
  title_size_pt: 26,
  alignment: "left",
  margin_inches: 1,
  page: "letter",
  spacing_after_pt: 8,
  line_spacing: 1.15,
  header: "",
  footer: "",
  page_numbers: false,
  orientation: "portrait",
  columns: 1
}

const BLOCK_TYPES = new Set([
  "title",
  "heading",
  "paragraph",
  "bullet",
  "numbered",
  "table",
  "quote",
  "code",
  "callout",
  "equation",
  "rule",
  "page_break",
  "chart",
  "contents",
  "references"
])

function asNumber(value: unknown, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function asText(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}

function asFlag(value: unknown) {
  if (typeof value === "boolean") return value
  if (typeof value === "string") return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase())
  return Boolean(value)
}

function normalizeRun(raw: unknown): DocxRun | null {
  if (!raw || typeof raw !== "object") return null
  const run = raw as Record<string, unknown>
  const text = asText(run.text)
  const note = asText(run.note)
  if (!text && !note) return null
  const next: DocxRun = { text }
  if (run.bold) next.bold = true
  if (run.italic) next.italic = true
  if (run.underline) next.underline = true
  const color = asText(run.color).replace("#", "")
  if (/^[0-9A-Fa-f]{6}$/.test(color)) next.color = color.toUpperCase()
  const highlight = asText(run.highlight)
  if (highlight) next.highlight = highlight
  const link = asText(run.link)
  if (/^(https?:|mailto:)/.test(link)) next.link = link
  if (note) next.note = note
  return next
}

function normalizeCell(raw: unknown): DocxCell {
  if (raw && typeof raw === "object") {
    const cell = raw as Record<string, unknown>
    const runs = Array.isArray(cell.runs)
      ? cell.runs.map(normalizeRun).filter((run): run is DocxRun => run !== null)
      : []
    const text = asText(cell.text)
    const note = asText(cell.note)
    if (!runs.length && !note) return text
    return { text, ...(runs.length ? { runs } : {}), ...(note ? { note } : {}) }
  }
  return String(raw ?? "")
}

function normalizeBlock(raw: unknown): DocxBlock | null {
  if (!raw || typeof raw !== "object") return null
  const block = raw as Record<string, unknown>
  const type = asText(block.type)
  if (!BLOCK_TYPES.has(type)) return null
  if (type === "rule" || type === "page_break" || type === "contents") {
    return { type }
  }
  if (type === "bullet" || type === "numbered" || type === "references") {
    const items = Array.isArray(block.items)
      ? block.items.map(item => String(item).trim()).filter(Boolean)
      : []
    return items.length ? { type, items } : null
  }
  if (type === "table") {
    const rows = Array.isArray(block.rows)
      ? block.rows
          .filter(row => Array.isArray(row))
          .map(row => (row as unknown[]).map(normalizeCell))
      : []
    if (!rows.length) return null
    const caption = asText(block.caption)
    return {
      type,
      rows,
      header: block.header !== false,
      ...(caption ? { caption } : {})
    }
  }
  if (type === "chart") {
    const categories = Array.isArray(block.categories)
      ? block.categories.map(item => String(item).trim()).filter(Boolean)
      : []
    const series = Array.isArray(block.series)
      ? block.series
          .filter(item => item && typeof item === "object")
          .map(item => {
            const rawSeries = item as Record<string, unknown>
            const values = Array.isArray(rawSeries.values)
              ? rawSeries.values.map(value => asNumber(value, 0))
              : []
            return { name: asText(rawSeries.name) || "Series", values }
          })
          .filter(item => item.values.length)
      : []
    if (!categories.length || !series.length) return null
    const caption = asText(block.caption)
    return {
      type,
      chart: asText(block.chart) || "column",
      title: asText(block.title),
      categories,
      series,
      ...(caption ? { caption } : {})
    }
  }
  const runs = Array.isArray(block.runs)
    ? block.runs.map(normalizeRun).filter((run): run is DocxRun => run !== null)
    : []
  const text = asText(block.text)
  const note = asText(block.note)
  if (type === "code") {
    return text ? { type, text, ...(asText(block.language) ? { language: asText(block.language) } : {}) } : null
  }
  if (!text && !note && !runs.length) return null
  const next: DocxBlock = {
    type: type as DocxBlock["type"],
    ...(text ? { text } : {}),
    ...(runs.length ? { runs } : {}),
    ...(note ? { note } : {})
  }
  if (type === "heading") next.level = Math.min(3, Math.max(1, asNumber(block.level, 1)))
  if (type === "quote" && asText(block.source)) next.source = asText(block.source)
  if (type === "callout") {
    const kind = asText(block.kind)
    next.kind = kind === "tip" || kind === "warning" ? kind : "note"
  }
  return next
}

export function parseDocumentEvent(event: Record<string, unknown>): DocxDocument | null {
  const id = String(event.id || event.document_id || "").trim()
  if (!/^doc_[a-f0-9]{12}$/.test(id)) return null
  const rawStyle =
    event.style && typeof event.style === "object"
      ? (event.style as Record<string, unknown>)
      : {}
  const alignment = asText(rawStyle.alignment) || DEFAULT_DOCX_STYLE.alignment
  const page = asText(rawStyle.page) || DEFAULT_DOCX_STYLE.page
  const orientation = asText(rawStyle.orientation) === "landscape" ? "landscape" : "portrait"
  const columns = Math.min(3, Math.max(1, Math.round(asNumber(rawStyle.columns, 1))))
  return {
    id,
    title: asText(event.title) || "Document",
    version: asNumber(event.version, 1),
    style: {
      font_body: asText(rawStyle.font_body) || DEFAULT_DOCX_STYLE.font_body,
      font_heading: asText(rawStyle.font_heading) || DEFAULT_DOCX_STYLE.font_heading,
      body_size_pt: asNumber(rawStyle.body_size_pt, DEFAULT_DOCX_STYLE.body_size_pt),
      heading_size_pt: asNumber(rawStyle.heading_size_pt, DEFAULT_DOCX_STYLE.heading_size_pt),
      title_size_pt: asNumber(rawStyle.title_size_pt, DEFAULT_DOCX_STYLE.title_size_pt),
      alignment: alignment === "center" || alignment === "justify" ? alignment : "left",
      margin_inches: asNumber(rawStyle.margin_inches, DEFAULT_DOCX_STYLE.margin_inches),
      page: page === "a4" ? "a4" : "letter",
      spacing_after_pt: asNumber(rawStyle.spacing_after_pt, DEFAULT_DOCX_STYLE.spacing_after_pt),
      line_spacing: asNumber(rawStyle.line_spacing, DEFAULT_DOCX_STYLE.line_spacing),
      header: asText(rawStyle.header),
      footer: asText(rawStyle.footer),
      page_numbers: asFlag(rawStyle.page_numbers),
      orientation,
      columns
    },
    blocks: Array.isArray(event.blocks)
      ? event.blocks.map(normalizeBlock).filter((block): block is DocxBlock => block !== null)
      : []
  }
}

export function fontStack(name: string) {
  const safe = name.replace(/["<>]/g, "")
  const serif = /georgia|garamond|cambria|times|liberation serif|palatino|merriweather/i.test(safe)
  const fallback = serif
    ? "Georgia, 'Times New Roman', serif"
    : "Calibri, Carlito, 'Segoe UI', sans-serif"
  return `"${safe}", "Cambria Math", "Segoe UI Symbol", ${fallback}`
}
