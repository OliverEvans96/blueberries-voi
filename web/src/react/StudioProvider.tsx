import { useEffect } from "react";
import { initStudio } from "./studioLogic";

type StudioProviderProps = {
  children: React.ReactNode;
};

/** Boots imperative D3 + adapter wiring after React layout mounts (T-121). */
export function StudioProvider({ children }: StudioProviderProps) {
  useEffect(() => {
    const app = document.getElementById("app");
    if (!app) return undefined;
    return initStudio(app);
  }, []);

  return <>{children}</>;
}
