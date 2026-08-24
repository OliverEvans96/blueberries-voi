import { useRef } from "react";
import { StudioLayout } from "./react/StudioLayout";
import { StudioProvider } from "./react/StudioProvider";

export function App() {
  const containerRef = useRef<HTMLDivElement>(null);
  return (
    <div ref={containerRef}>
      <StudioProvider containerRef={containerRef}>
        <StudioLayout />
      </StudioProvider>
    </div>
  );
}
