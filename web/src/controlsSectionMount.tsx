import { createRoot } from "react-dom/client";
import { SectionControlsView } from "./react/SectionControls";
import {
  DEFAULT_CONTROLLER_CONTROLS,
  type ControlsCallbacks,
  type ControlsState,
  type ControllerControlsState,
} from "./controls";
import type { SectionId } from "./sections";

export function mountSectionControls(
  root: HTMLElement,
  initial: ControlsState,
  cb: Pick<
    ControlsCallbacks,
    | "onEconomicsChange"
    | "onConfigChange"
    | "onControllerChange"
    | "onSetObsScenario"
  >,
  onCaseSizeChange?: (caseSize: number) => void,
  initialController: ControllerControlsState = DEFAULT_CONTROLLER_CONTROLS,
): {
  update: (s: ControlsState) => void;
  showSection: (id: SectionId) => void;
  updateController: (s: ControllerControlsState) => void;
} {
  const domRoot = createRoot(root);
  let state = initial;
  let controllerState = { ...initialController };
  let visibleSection: SectionId = "play";

  function render(): void {
    domRoot.render(
      <SectionControlsView
        state={state}
        controllerState={controllerState}
        visibleSection={visibleSection}
        callbacks={cb}
        onCaseSizeChange={onCaseSizeChange}
      />,
    );
  }

  render();

  return {
    update(s) {
      state = s;
      render();
    },
    updateController(s) {
      controllerState = { ...s };
      render();
    },
    showSection(id) {
      visibleSection = id;
      render();
    },
  };
}
