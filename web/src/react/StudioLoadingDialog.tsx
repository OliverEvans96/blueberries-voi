import { useEffect, useRef, type RefObject } from "react";
import { createPortal } from "react-dom";
import "../styles/studioLoadingDialog.css";

export type StudioLoadingDialogProps = {
  visible: boolean;
  message: string;
  portalContainerRef?: RefObject<HTMLElement | null>;
};

/** Subtle delayed loading card — portaled over the studio shell (T-149). */
export function StudioLoadingDialog({
  visible,
  message,
  portalContainerRef,
}: StudioLoadingDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const host =
    portalContainerRef?.current ??
    document.getElementById("studio-loading-host");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (visible) {
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
  }, [visible]);

  if (!host || !visible) return null;

  return createPortal(
    <dialog
      ref={dialogRef}
      className="studio-loading-dialog"
      aria-labelledby="studio-loading-message"
    >
      <div
        className="studio-loading-dialog-card"
        role="status"
        id="studio-loading-message"
      >
        <span
          className="studio-loading-dialog-dot engine-status-dot"
          aria-hidden="true"
        />
        <span>{message}</span>
      </div>
    </dialog>,
    host,
  );
}
