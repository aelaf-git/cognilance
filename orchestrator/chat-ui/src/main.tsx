import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RootRouter } from "./Router";
import "./index.css";

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

const nativeFetch = window.fetch.bind(window);
window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
  const headers = new Headers(init?.headers);
  if (!headers.has("X-User-Timezone")) {
    headers.set("X-User-Timezone", browserTimezone());
  }
  return nativeFetch(input, { ...init, headers });
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RootRouter />
  </StrictMode>,
);
