import { redirect } from "next/navigation"

/** Home is never shown; middleware also sends `/` to chat. */
export default function HomePage() {
  redirect("/local/chat")
}
