import {
  STUDIO_BLOG_POST_URL,
  STUDIO_DOCS_URL,
  STUDIO_GITHUB_URL,
} from "../studioLinks";
import { useStudioEmbed } from "./StudioEmbedContext";

const EXTERNAL_LINK_PROPS = {
  target: "_blank",
  rel: "noopener noreferrer",
} as const;

/** Blog post link beside the studio title. */
export function TitleBarBlogLink() {
  const { blogPostUrl } = useStudioEmbed();
  const href = blogPostUrl ?? STUDIO_BLOG_POST_URL;
  return (
    <a
      className="title-bar-blog-link"
      href={href}
      {...EXTERNAL_LINK_PROPS}
    >
      Read the blog post
    </a>
  );
}

/** Docs + GitHub actions immediately left of the settings control. */
export function TitleBarExternalActions() {
  return (
    <>
      <a
        className="title-bar-action title-bar-action--docs"
        href={STUDIO_DOCS_URL}
        aria-label="Documentation"
        {...EXTERNAL_LINK_PROPS}
      >
        <span className="title-bar-action-icon" aria-hidden="true" />
        <span className="title-bar-action-label">Docs</span>
      </a>
      <a
        className="title-bar-action title-bar-action--github"
        href={STUDIO_GITHUB_URL}
        aria-label="GitHub repository"
        {...EXTERNAL_LINK_PROPS}
      >
        <span className="title-bar-action-icon" aria-hidden="true" />
      </a>
    </>
  );
}
