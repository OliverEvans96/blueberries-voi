/** Delay before showing the studio loading dialog (T-149). */
export const STUDIO_LOADING_DELAY_MS = 750;

export type DelayedLoadingHandle = {
  begin(): void;
  end(): void;
};

/** Ref-counted delayed visibility — skips the dialog for fast operations. */
export function createDelayedLoadingHandle(
  onVisibleChange: (visible: boolean) => void,
  delayMs = STUDIO_LOADING_DELAY_MS,
): DelayedLoadingHandle {
  let refCount = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let visible = false;

  function setVisible(next: boolean): void {
    if (visible === next) return;
    visible = next;
    onVisibleChange(next);
  }

  function begin(): void {
    refCount += 1;
    if (refCount === 1) {
      timer = setTimeout(() => {
        if (refCount > 0) setVisible(true);
      }, delayMs);
    }
  }

  function end(): void {
    if (refCount <= 0) return;
    refCount -= 1;
    if (refCount === 0) {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      setVisible(false);
    }
  }

  return { begin, end };
}
