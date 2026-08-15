import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import { PlayChromeView } from "./react/PlayChrome";
import type {
  ControlsCallbacks,
  ControlsState,
  PlayChromeOpts,
} from "./controls";

function snap(qty: number, caseSize: number): number {
  if (qty <= 0) return 0;
  const cs = Math.max(1, Math.round(caseSize));
  return Math.round(qty / cs) * cs;
}

export function mountPlayChrome(
  root: HTMLElement,
  initial: ControlsState,
  cb: Pick<
    ControlsCallbacks,
    | "onOrderChange"
    | "onAdvance"
    | "onReset"
    | "onAutopilotPlay"
    | "onAutopilotPause"
    | "onShowTruthChange"
  >,
  opts?: PlayChromeOpts,
): {
  update: (s: ControlsState) => void;
  setOrderFromCaseChange: (qty: number, caseSize: number) => void;
  setAutopilotRunning: (running: boolean) => void;
  destroy: () => void;
} {
  const domRoot = createRoot(root);
  let state = initial;
  let autopilotRunning = false;
  let showTruth = opts?.showTruth ?? false;
  const truthClassTarget = opts?.truthClassTarget;

  function render(notifyTruthOnMount: boolean): void {
    flushSync(() => {
      domRoot.render(
        <PlayChromeView
          state={state}
          autopilotRunning={autopilotRunning}
          showTruth={showTruth}
          truthClassTarget={truthClassTarget ?? null}
          notifyTruthOnMount={notifyTruthOnMount}
          callbacks={cb}
        />,
      );
    });
  }

  render(false);

  return {
    update(s) {
      state = s;
      render(true);
    },
    setOrderFromCaseChange(qty, cs) {
      state = {
        ...state,
        orderQty: snap(qty, cs),
        config: { ...state.config, case_size: cs },
      };
      cb.onOrderChange(snap(qty, cs));
      render(true);
    },
    setAutopilotRunning(running) {
      autopilotRunning = running;
      render(true);
    },
    destroy() {
      flushSync(() => domRoot.unmount());
    },
  };
}
