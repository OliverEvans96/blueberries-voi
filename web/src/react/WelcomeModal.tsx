import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { STUDIO_DOCS_URL } from "../studioLinks";
import "../styles/welcomeModal.css";

export type WelcomeModalProps = {
  open: boolean;
  onDismiss: () => void;
  portalContainerRef?: RefObject<HTMLElement | null>;
};

type WelcomeStep = {
  label: string;
  title: string;
  body: string;
};

const STEPS: WelcomeStep[] = [
  {
    label: "The model",
    title: "A hidden shelf of blueberries",
    body: "Behind the scenes, a physics model ages every carton, sells what customers buy, and spoils what sits too long. That hidden state is the ground truth — and like a real produce manager, you rarely know it exactly. With hundreds of punnets on the shelf, small gaps in what you can see turn into real uncertainty about what's still fresh and what's quietly going soft.",
  },
  {
    label: "The filter",
    title: "A best guess from clues",
    body: "You can't see the shelf directly — only receipts, scans, and delivery notes. A “filter” turns those clues into a running best guess about what's really back there.",
  },
  {
    label: "The controller",
    title: "An order, every day",
    body: "Each day, a “controller” looks at that guess and decides how much to order, weighing empty shelves against spoiled cartons. That controller can be you — a produce manager placing one order — or Autopilot mode, where an algorithm takes the same decision loop for you.",
  },
];

/** Large static welcome dialog shown while the WASM engine loads. */
export function WelcomeModal({
  open,
  onDismiss,
  portalContainerRef,
}: WelcomeModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const scopeRef = useRef<HTMLSpanElement>(null);

  // Default host resolves to the nearest `.bv-studio` scope root rather than
  // the (aria-hidden) drawer/dialog portal container — a modal dialog nested
  // under an aria-hidden ancestor is invisible to assistive tech even though
  // native <dialog> promotes it to the top layer visually. Resolved post-mount
  // since refs aren't attached yet during the render that produces them.
  const [fallbackHost, setFallbackHost] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!portalContainerRef) {
      setFallbackHost(
        scopeRef.current?.closest<HTMLElement>(".bv-studio") ??
          document.body,
      );
    }
  }, [portalContainerRef]);

  const host = portalContainerRef?.current ?? fallbackHost;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      try {
        if (typeof dialog.showModal === "function" && !dialog.open) {
          dialog.showModal();
        } else if (!dialog.hasAttribute("open")) {
          dialog.setAttribute("open", "");
        }
      } catch {
        dialog.setAttribute("open", "");
      }
    } else if (dialog.open) {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  }, [open, host]);

  const marker = <span ref={scopeRef} hidden aria-hidden="true" />;

  if (!host || !open) return marker;

  return (
    <>
      {marker}
      {createPortal(
        <dialog
          ref={dialogRef}
          className="welcome-modal"
          aria-labelledby="welcome-modal-title"
          onClose={onDismiss}
          onCancel={onDismiss}
        >
          <button
            type="button"
            className="welcome-modal-close"
            aria-label="Close welcome"
            onClick={onDismiss}
          >
            &times;
          </button>

          <h2 id="welcome-modal-title" className="welcome-modal-title">
            Welcome to Blueberry Aisle
          </h2>

          <p className="welcome-modal-lede">
            You're running a small produce aisle. Blueberries arrive, sit,
            sell, and sometimes spoil — every day you decide how many more to
            order.
          </p>

          <p className="welcome-modal-role">
            <strong>Your role:</strong> store manager. Place one order a day
            and watch the shelf live with it — happy customers, wasted
            cartons, or empty bins.
          </p>

          <div className="welcome-modal-steps">
            {STEPS.map((step, i) => (
              <div className="welcome-modal-step" key={step.label}>
                <div className="welcome-modal-step-heading">
                  <span className="welcome-modal-step-index" aria-hidden="true">
                    {i + 1}
                  </span>
                  <p className="welcome-modal-step-label">{step.label}</p>
                </div>
                <p className="welcome-modal-step-title">{step.title}</p>
                <p className="welcome-modal-step-body">{step.body}</p>
              </div>
            ))}
          </div>

          <p className="welcome-modal-footer-note">
            Turn a knob, then hit Start exploring to watch these three pieces
            play out together. The{" "}
            <a href={STUDIO_DOCS_URL} target="_blank" rel="noopener noreferrer">
              docs
            </a>{" "}
            cover the details — this is just the map.
          </p>

          <button
            type="button"
            className="welcome-modal-cta"
            onClick={onDismiss}
          >
            Start exploring
          </button>
        </dialog>,
        host,
      )}
    </>
  );
}
