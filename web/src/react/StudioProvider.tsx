import { useEffect, type RefObject } from "react";
import { initInfoTipPortal } from "../infoTipPortal";
import {
  StudioEmbedContext,
  type StudioEmbedContextValue,
} from "./StudioEmbedContext";
import { initStudio } from "./studioLogic";

export type StudioProviderProps = StudioEmbedContextValue & {
  children: React.ReactNode;
  /** Embed mount root; defaults to `#app` for standalone dev. */
  containerRef?: RefObject<HTMLElement | null>;
};

/** Boots imperative D3 + adapter wiring after React layout mounts (T-121). */
export function StudioProvider({
  children,
  containerRef,
  blogPostUrl,
}: StudioProviderProps) {
  useEffect(() => {
    const app = containerRef?.current ?? document.getElementById("app");
    if (!app) {
      console.error(
        "StudioProvider: no mount container found. Pass containerRef or ensure #app exists.",
      );
      return undefined;
    }
    const cleanupStudio = initStudio(app);
    const cleanupInfoTips = initInfoTipPortal(app);
    return () => {
      cleanupInfoTips();
      cleanupStudio();
    };
  }, [containerRef]);

  return (
    <StudioEmbedContext.Provider value={{ blogPostUrl }}>
      {children}
    </StudioEmbedContext.Provider>
  );
}
