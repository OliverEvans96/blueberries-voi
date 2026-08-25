import type MarkdownIt from "markdown-it";

/** Wrap `/figures/` markdown images in <figure> with a visible <figcaption>. */
export function markdownFigures(md: MarkdownIt): void {
  const defaultImageRender =
    md.renderer.rules.image ??
    ((tokens, idx, options, _env, self) =>
      self.renderToken(tokens, idx, options));

  md.renderer.rules.image = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    const src = token.attrGet("src") ?? "";
    const alt = token.content;

    if (!src.includes("/figures/")) {
      return defaultImageRender(tokens, idx, options, env, self);
    }

    if (alt) {
      token.content = "";
      token.attrSet("alt", "");
    }

    const imgHtml = defaultImageRender(tokens, idx, options, env, self)
      .replace(/\salt="[^"]*"/, ' alt=""');
    if (!alt) {
      return `<figure class="doc-figure">${imgHtml}</figure>`;
    }

    const caption = md.utils.escapeHtml(alt);
    return `<figure class="doc-figure">${imgHtml}<figcaption class="doc-figure-caption">${caption}</figcaption></figure>`;
  };
}
