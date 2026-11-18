const FORMULA =
  /\\(?:frac|sqrt|mathbf|mathrm|mathbb|text|vec|hat|bar|dot|partial|nabla|cdot|times|sum|int|infty|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|nu|pi|rho|sigma|tau|phi|psi|omega|Lambda|Gamma|Delta|Omega)|_\{|\^\{/
const CODE_WORD =
  /[;{}]|=>|\b(const|let|var|function|return|class|import|from|if|for|while)\b/

function maskRegions(text: string, pattern: RegExp, masked: string[]): string {
  return text.replace(pattern, match => {
    const token = `\u0000${masked.length}\u0000`
    masked.push(match)
    return token
  })
}

function unescapeCommands(source: string): string {
  return source.replace(/\\{2,}(?=[a-zA-Z])/g, "\\")
}

function isFormula(source: string): boolean {
  return FORMULA.test(source)
}

function isShortEquation(source: string): boolean {
  const text = source.trim()
  if (!text.includes("=") || text.length > 40 || CODE_WORD.test(text)) return false
  return /^[A-Za-z0-9\s=+\-*/^_().,]+$/.test(text)
}

function isLoneIdentifier(source: string): boolean {
  return /^[A-Za-z]$/.test(source.trim())
}

function answerHasEquation(text: string): boolean {
  if (/\$\$[\s\S]+?\$\$/.test(text)) return true
  if (/\$[^$\n]+\$/.test(text)) return true
  for (const match of text.matchAll(/`([^`\n]+)`/g)) {
    const source = unescapeCommands(match[1])
    if (isFormula(source) || isShortEquation(source)) return true
  }
  return false
}

function displayBlock(body: string): string {
  return `\n\n$$\n${unescapeCommands(body.trim())}\n$$\n\n`
}

function repairCutOffDisplay(text: string): string {
  // `$|` ends a display equation only when the pipe does not continue
  // math, as in the ket `$|\psi\rangle$`.
  return text.replace(
    /\$\$[ \t]*(?:\n[ \t]*)?([^$\n]*?)\$\|(?![A-Za-z0-9\\{(|[])/g,
    (match, body: string) => {
      const normalized = unescapeCommands(body)
      if (!normalized.trim()) return match
      if (!isFormula(normalized) && !normalized.includes("=")) return match
      return displayBlock(body)
    }
  )
}

function liftDisplayMath(text: string): string {
  let next = repairCutOffDisplay(text)
  next = next.replace(/\$\$([\s\S]*?)\$\$/g, (_, body: string) => displayBlock(body))
  return next.replace(/\$\$([^$\n]+)\$/g, (match, body: string) => {
    const normalized = unescapeCommands(body)
    if (!isFormula(normalized) && !normalized.includes("=")) return match
    return displayBlock(body)
  })
}

function unescapeInlineMath(text: string): string {
  return text.replace(/\$([^$\n]+)\$/g, (_, body: string) => `$${unescapeCommands(body)}$`)
}

function promoteCodeSpans(text: string, mathContext: boolean): string {
  return text.replace(/`([^`\n]+)`/g, (match, source: string) => {
    const normalized = unescapeCommands(source)
    const equation = isFormula(normalized) || isShortEquation(normalized)
    if (equation || (mathContext && isLoneIdentifier(normalized))) return `$${normalized}$`
    return match
  })
}

function separateTables(text: string): string {
  const lines = text.split("\n")
  const out: string[] = []
  const isRow = (line: string) => /^\s*\|.+\|\s*$/.test(line)
  for (const raw of lines) {
    let line = raw
    const inline = line.match(/^(.*\S)\s+(\|.+\|\s*)$/)
    if (inline && !isRow(line)) {
      out.push(inline[1])
      out.push("")
      line = inline[2]
    }
    const previous = out.length ? out[out.length - 1] : ""
    if (isRow(line) && previous.trim() && !isRow(previous)) out.push("")
    out.push(line)
  }
  return out.join("\n")
}

function splitNumberedRuns(text: string): string {
  const matches = [...text.matchAll(/(\d+)\.\s+\*\*/g)].map(match => ({
    index: match.index ?? 0,
    number: Number(match[1])
  }))
  if (matches.length < 2) return text

  const breaks = new Set<number>()
  let run: { index: number; number: number }[] = []
  const flush = () => {
    const sequential =
      run.length >= 2 &&
      run[0].number === 1 &&
      run.every((item, index) => item.number === index + 1)
    if (sequential) {
      for (const item of run) breaks.add(item.index)
    }
    run = []
  }

  for (const match of matches) {
    const between = run.length ? text.slice(run[run.length - 1].index, match.index) : ""
    const next = run.length === 0 ? match.number === 1 : match.number === run[run.length - 1].number + 1
    if (!next || between.includes("\n\n")) {
      flush()
      if (match.number === 1) run = [match]
      continue
    }
    run.push(match)
  }
  flush()
  if (!breaks.size) return text

  let out = ""
  let cursor = 0
  for (const index of [...breaks].sort((a, b) => a - b)) {
    let cut = index
    while (cut > cursor && text[cut - 1] === " ") cut -= 1
    const atLineStart = cut === 0 || text[cut - 1] === "\n"
    out += text.slice(cursor, cut)
    if (!atLineStart) out += "\n"
    cursor = index
  }
  return out + text.slice(cursor)
}

export function prepareAnswer(content: string): string {
  const masked: string[] = []
  let text = maskRegions(content, /```[\s\S]*?```/g, masked)
  const mathContext = answerHasEquation(text)
  text = liftDisplayMath(text)
  text = unescapeInlineMath(text)
  text = promoteCodeSpans(text, mathContext)
  text = separateTables(text)
  text = splitNumberedRuns(text)
  text = text.replace(/\n{3,}/g, "\n\n")
  return text.replace(/\u0000(\d+)\u0000/g, (_, index: string) => masked[Number(index)] ?? "")
}
