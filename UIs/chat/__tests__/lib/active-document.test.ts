import { toChatMessages, withActiveDocument } from "@/lib/cognilance-client"
import { DocxDocument } from "@/lib/docx-document"

const document: DocxDocument = {
  id: "doc_abcabcabcabc",
  title: "History of Napoleon",
  version: 2,
  style: {
    font_body: "Times New Roman",
    font_heading: "Times New Roman",
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
  },
  blocks: [{ type: "paragraph", text: "Napoleon was born in Corsica." }]
}

describe("withActiveDocument", () => {
  it("puts the saved file on the latest assistant message", () => {
    const messages = toChatMessages(
      [
        { id: 1, role: "user", content: "Write it", created_at: "2026-11-13T00:00:00Z" },
        { id: 2, role: "assistant", content: "The file is ready.", created_at: "2026-11-13T00:00:01Z" },
        { id: 3, role: "user", content: "Change the font", created_at: "2026-11-13T00:00:02Z" },
        { id: 4, role: "assistant", content: "Updated.", created_at: "2026-11-13T00:00:03Z" }
      ],
      "conv-1"
    )

    const restored = withActiveDocument(messages, document)

    expect(restored[1].document).toBeUndefined()
    expect(restored[3].document).toMatchObject({
      id: "doc_abcabcabcabc",
      title: "History of Napoleon",
      blocks: [{ type: "paragraph", text: "Napoleon was born in Corsica." }]
    })
  })
})
