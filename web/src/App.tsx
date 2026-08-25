import { useRef } from "react";
import { StudioLayout } from "./react/StudioLayout";
import { StudioProvider } from "./react/StudioProvider";

export type AppProps = {
  /** Override the default blog post URL in the title bar. */
  blogPostUrl?: string;
};

export function App({ blogPostUrl }: AppProps = {}) {
  const containerRef = useRef<HTMLDivElement>(null);
  return (
    <div ref={containerRef}>
      <StudioProvider containerRef={containerRef} blogPostUrl={blogPostUrl}>
        <StudioLayout />
      </StudioProvider>
    </div>
  );
}
