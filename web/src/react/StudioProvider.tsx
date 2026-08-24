import { useEffect, type RefObject } from "react";
import { initStudio } from "./studioLogic";

export type StudioProviderProps = {
  children: React.ReactNode;
  /** Embed mount root; defaults to `#app` for standalone dev. */
  containerRef?: RefObject<HTMLElement | null>;
};

/** Boots imperative D3 + adapter wiring after React layout mounts (T-121). */
export function StudioProvider({
  children,
  containerRef,
}: StudioProviderProps) {
  useEffect(() => {
    const app = containerRef?.current ?? document.getElementById("app");
    if (!app) {
      console.error(
        "StudioProvider: no mount container found. Pass containerRef or ensure #app exists.",
      );
      return undefined;
    }
    return initStudio(app);
  }, [containerRef]);

  return <>{children}</>;
}
