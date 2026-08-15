import { useEffect, useRef } from "react";
import {
  mountSectionControlsDom,
  type ControlsCallbacks,
  type ControlsState,
  type ControllerControlsState,
} from "../controls";
import type { SectionId } from "../sections";

export type SectionControlsViewProps = {
  state: ControlsState;
  controllerState: ControllerControlsState;
  visibleSection: SectionId;
  callbacks: Pick<
    ControlsCallbacks,
    | "onEconomicsChange"
    | "onConfigChange"
    | "onControllerChange"
    | "onSetObsScenario"
  >;
  onCaseSizeChange?: (caseSize: number) => void;
};

/** React host for legacy section-controls DOM (exact HTML + listeners). */
export function SectionControlsView({
  state,
  controllerState,
  visibleSection,
  callbacks,
  onCaseSizeChange,
}: SectionControlsViewProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<ReturnType<typeof mountSectionControlsDom> | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    apiRef.current = mountSectionControlsDom(
      host,
      state,
      callbacks,
      onCaseSizeChange,
      controllerState,
    );
    apiRef.current.showSection(visibleSection);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount once
  }, []);

  useEffect(() => {
    apiRef.current?.update(state);
  }, [state]);

  useEffect(() => {
    apiRef.current?.updateController(controllerState);
  }, [controllerState]);

  useEffect(() => {
    apiRef.current?.showSection(visibleSection);
  }, [visibleSection]);

  return <div ref={hostRef} />;
}
