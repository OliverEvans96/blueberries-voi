import { createContext, useContext } from "react";

export type StudioEmbedContextValue = {
  /** Override the default blog post URL shown in the title bar. */
  blogPostUrl?: string;
};

export const StudioEmbedContext = createContext<StudioEmbedContextValue>({});

export function useStudioEmbed(): StudioEmbedContextValue {
  return useContext(StudioEmbedContext);
}
