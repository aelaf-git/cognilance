import { prepareAnswer } from "@/lib/prepare-answer"

const NEWTON = [
  "Here is an overview of each law:",
  "",
  "1. **First Law (Law of Inertia):** An object remains at rest or in uniform motion. 2. **Second Law (Law of Momentum):** The rate of change of momentum is proportional to the force. Mathematically, `\\mathbf{F} = \\frac{d\\mathbf{p}}{dt}`. For a system with constant mass `m`, this simplifies to `\\mathbf{F} = m\\mathbf{a}`. 3. **Third Law (Action and Reaction):** The forces are equal and opposite. Mathematically, `\\mathbf{F}_{12} = -\\mathbf{F}_{21}`."
].join("\n")

describe("prepareAnswer", () => {
  it("turns the Newton reply into a list and leaves formulas out of backticks", () => {
    const prepared = prepareAnswer(NEWTON)

    expect(prepared).toContain("\n2. **Second Law")
    expect(prepared).toContain("\n3. **Third Law")
    expect(prepared).toContain("$\\mathbf{F} = \\frac{d\\mathbf{p}}{dt}$")
    expect(prepared).toContain("$\\mathbf{F} = m\\mathbf{a}$")
    expect(prepared).toContain("$\\mathbf{F}_{12} = -\\mathbf{F}_{21}$")
    expect(prepared).toContain("$m$")
    expect(prepared).not.toContain("`\\mathbf{F}")
    expect(prepared).not.toContain("`m`")
  })

  it("leaves an ordinary sentence that mentions 2. as one paragraph", () => {
    const sentence = "The report is version 2. It shipped yesterday."
    expect(prepareAnswer(sentence)).toBe(sentence)
  })

  it("leaves math that is already delimited", () => {
    const answer = "The force is $\\mathbf{F} = m\\mathbf{a}$."
    expect(prepareAnswer(answer)).toBe(answer)
  })

  it("lifts a glued display equation and turns short formulas into math", () => {
    const reply = [
      "Momentum is `p = mv`. 1. **Historical Formulation:** The force equals the rate of change. $$\\\\vec{F} = \\\\frac{d\\\\vec{p}}{dt}$$",
      "2. **Expanding the Derivative:** `\\\\vec{p} = m\\\\vec{v}`, and the mass `m` is constant."
    ].join("\n")
    const prepared = prepareAnswer(reply)

    expect(prepared).toContain("\n$$\n\\vec{F} = \\frac{d\\vec{p}}{dt}\n$$\n")
    expect(prepared).toContain("$p = mv$")
    expect(prepared).toContain("$\\vec{p} = m\\vec{v}$")
    expect(prepared).toContain("$m$")
    expect(prepared).not.toContain("$$\\\\")
    expect(prepared).not.toContain("`p = mv`")
  })

  it("lifts a display equation whose closer was cut off by a pipe", () => {
    const reply = "The force acts. $$\\vec{F} = \\frac{d\\vec{p}}{dt}$|"
    const prepared = prepareAnswer(reply)
    expect(prepared).toContain("\n$$\n\\vec{F} = \\frac{d\\vec{p}}{dt}\n$$\n")
    expect(prepared).not.toContain("$|")
  })

  it("keeps a ket and repairs only the display equation that ends in a pipe", () => {
    const reply = [
      "Their commutator is:",
      "$$\\left[\\hat{x}, \\hat{p}\\right] = i\\hbar$$",
      "",
      "in any state $|\\psi\\rangle$ satisfies:",
      "$$\\sigma_x^2 \\sigma_p^2 \\ge \\frac{1}{4} \\left| \\langle i\\hbar \\rangle \\right|^2 = \\frac{\\hbar^2}{4}$|"
    ].join("\n")
    const prepared = prepareAnswer(reply)
    expect(prepared).toContain("$|\\psi\\rangle$")
    expect(prepared).toContain("\n$$\n\\sigma_x^2 \\sigma_p^2 \\ge \\frac{1}{4} \\left| \\langle i\\hbar \\rangle \\right|^2 = \\frac{\\hbar^2}{4}\n$$\n")
    expect(prepared).not.toMatch(/\$\$\s*\\psi/)
  })

  it("lifts a display equation when the broken closer is on the next line", () => {
    const reply = [
      "The force acts.",
      "$$",
      "\\vec{F} = \\frac{d\\vec{p}}{dt}$|",
      "Since momentum $\\vec{p} = m\\vec{v}$, the mass $m$ is constant.",
      "$$\\vec{F} = m\\vec{a}$|"
    ].join("\n")
    const prepared = prepareAnswer(reply)
    expect(prepared).toContain("\n$$\n\\vec{F} = \\frac{d\\vec{p}}{dt}\n$$\n")
    expect(prepared).toContain("\n$$\n\\vec{F} = m\\vec{a}\n$$\n")
    expect(prepared).toContain("$\\vec{p} = m\\vec{v}$")
    expect(prepared).not.toContain("$|")
  })

  it("keeps a lone identifier in a programming reply", () => {
    const reply = "Use the variable `m` in the loop."
    expect(prepareAnswer(reply)).toBe(reply)
  })

  it("gives a pipe table a blank line before it", () => {
    const reply = "Compare the laws.\n| Law | Idea |\n| --- | --- |\n| First | Inertia |"
    expect(prepareAnswer(reply)).toContain("Compare the laws.\n\n| Law | Idea |")
  })
})
