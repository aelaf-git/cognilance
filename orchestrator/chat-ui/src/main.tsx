import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RootRouter } from "./Router";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RootRouter />
  </StrictMode>,
);
