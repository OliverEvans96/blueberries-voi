/**
 * Publishable studio entry for Astro / Vite hosts.
 *
 * Styles (required):
 * `import "@oliverevans96/blueberries-voi-studio/styles.css"`
 */
import "./styles.css";

export { App as Studio } from "./App";
export type { AppProps as StudioProps } from "./App";
export { StudioProvider } from "./react/StudioProvider";
export type { StudioProviderProps } from "./react/StudioProvider";
export {
  StudioEmbedContext,
  useStudioEmbed,
} from "./react/StudioEmbedContext";
export type { StudioEmbedContextValue } from "./react/StudioEmbedContext";
export { StudioLayout } from "./react/StudioLayout";
