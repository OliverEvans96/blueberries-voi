import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Studio } from "@oliverevans96/blueberries-voi-studio";
import "@oliverevans96/blueberries-voi-studio/styles.css";

const rootEl = document.getElementById("app");
if (!rootEl) throw new Error("#app missing");

createRoot(rootEl).render(
  <StrictMode>
    <Studio />
  </StrictMode>,
);
