import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { App } from "./App";

const rootEl = document.getElementById("app");
if (!rootEl) throw new Error("#app missing");

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
