/**
 * Title bar external links — blog, docs, GitHub.
 */
// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import {
  STUDIO_BLOG_POST_URL,
  STUDIO_DOCS_URL,
  STUDIO_GITHUB_URL,
} from "../studioLinks";
import { StudioEmbedContext } from "./StudioEmbedContext";
import { TitleBarBlogLink, TitleBarExternalActions } from "./TitleBarLinks";

describe("TitleBarLinks", () => {
  it("blog link points at the published blog post", () => {
    const { container } = render(createElement(TitleBarBlogLink));
    const link = container.querySelector("a.title-bar-blog-link");
    expect(link).not.toBeNull();
    expect(link).toHaveAttribute("href", STUDIO_BLOG_POST_URL);
    expect(link?.textContent).toBe("Read the blog post");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("blog link uses blogPostUrl from StudioEmbedContext when provided", () => {
    const customUrl = "https://example.com/my-post";
    const { container } = render(
      createElement(
        StudioEmbedContext.Provider,
        { value: { blogPostUrl: customUrl } },
        createElement(TitleBarBlogLink),
      ),
    );
    const link = container.querySelector("a.title-bar-blog-link");
    expect(link).toHaveAttribute("href", customUrl);
  });

  it("external actions include docs (icon + label) and GitHub (icon only)", () => {
    const { container } = render(createElement(TitleBarExternalActions));
    const docs = container.querySelector("a.title-bar-action--docs");
    const github = container.querySelector("a.title-bar-action--github");
    expect(docs).not.toBeNull();
    expect(github).not.toBeNull();
    expect(docs).toHaveAttribute("href", STUDIO_DOCS_URL);
    expect(github).toHaveAttribute("href", STUDIO_GITHUB_URL);
    expect(docs?.querySelector(".title-bar-action-label")?.textContent).toBe(
      "Docs",
    );
    expect(github?.querySelector(".title-bar-action-label")).toBeNull();
    expect(docs).toHaveAttribute("aria-label", "Documentation");
    expect(github).toHaveAttribute("aria-label", "GitHub repository");
  });
});
