/**
 * Studio embed context — optional host overrides (blogPostUrl).
 */
// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { StudioProvider } from "./StudioProvider";
import { TitleBarBlogLink } from "./TitleBarLinks";
import { STUDIO_BLOG_POST_URL } from "../studioLinks";

describe("StudioEmbedContext", () => {
  it("StudioProvider passes blogPostUrl to title bar consumers", () => {
    const customUrl = "https://embed.example.com/article";
    const { container } = render(
      createElement(
        StudioProvider,
        { blogPostUrl: customUrl },
        createElement(TitleBarBlogLink),
      ),
    );
    expect(
      container.querySelector("a.title-bar-blog-link"),
    ).toHaveAttribute("href", customUrl);
  });

  it("StudioProvider defaults blog link to STUDIO_BLOG_POST_URL", () => {
    const { container } = render(
      createElement(StudioProvider, null, createElement(TitleBarBlogLink)),
    );
    expect(
      container.querySelector("a.title-bar-blog-link"),
    ).toHaveAttribute("href", STUDIO_BLOG_POST_URL);
  });
});
