import { useEffect, useState } from "react";

const SHORTCUTS = [
  { keys: "1–8", action: "Jump to studio section" },
  { keys: "← →", action: "Previous / next section" },
  { keys: "↑ ↓", action: "Previous / next section" },
  { keys: "?", action: "Open this help" },
  { keys: "T", action: "Toggle sim truth overlay (when focused)" },
];

export function ShortcutHelp() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (event.key === "?") {
        event.preventDefault();
        setOpen((v) => !v);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <button
        type="button"
        className="shortcut-help-trigger"
        aria-label="Keyboard shortcuts"
        onClick={() => setOpen(true)}
      >
        ?
      </button>
      {open ? (
        <dialog className="shortcut-help-modal" open aria-label="Keyboard shortcuts">
          <header>
            <h2>Keyboard shortcuts</h2>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close">
              ×
            </button>
          </header>
          <ul>
            {SHORTCUTS.map((s) => (
              <li key={s.keys}>
                <kbd>{s.keys}</kbd> {s.action}
              </li>
            ))}
          </ul>
        </dialog>
      ) : null}
    </>
  );
}
