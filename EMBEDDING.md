# Embedding the Blueberry Studio

The browser studio ships as **`@oliverevans96/blueberries-voi-studio`**, a React 19
library with scoped CSS under `.bv-studio` (T-142/T-143). WASM runs in a bundled
module worker (T-144).

## Install from GitHub Releases

### Prod (auto-updated on every `main` push)

Once `packaging/github-workflows/release-studio.yml` is copied to
`.github/workflows/` and this repo’s embed work is on `main`, CI publishes a
moving release tag **`studio-latest`** with a **stable tarball filename**:

```json
{
  "dependencies": {
    "@oliverevans96/blueberries-voi-studio": "https://github.com/OliverEvans96/blueberries-voi/releases/download/studio-latest/oliverevans96-blueberries-voi-studio-latest.tgz"
  }
}
```

Re-run `pnpm install` / `npm install` in your Astro site after each `main` push
to pick up the new build (lockfile integrity hash will change when the tarball
changes).

The versioned filename on `studio-latest` (for example
`oliverevans96-blueberries-voi-studio-0.1.1.tgz`) updates with
`web/package.json` but is **not** immutable — both assets on that release are
overwritten on every publish.

### Immutable pin (recommended for certainty)

After each green CI run on `main`, the release workflow also creates
**`studio-v{version}`** (for example `studio-v0.1.1`) the first time that
semver appears. These releases attach **only** the versioned tarball — no
`-latest.tgz` alias — so the URL and filename stay fixed.

Manual tag pushes `studio-v*` (not legacy Python `v*`) publish the same
immutable asset shape:

```json
{
  "dependencies": {
    "@oliverevans96/blueberries-voi-studio": "https://github.com/OliverEvans96/blueberries-voi/releases/download/studio-v0.1.1/oliverevans96-blueberries-voi-studio-0.1.1.tgz"
  }
}
```

### Version bumps (contributors)

Changes under publishable paths (`web/src/`, `web/vite.lib.config.ts`,
`web/scripts/`, `crates/voi_core/`, `crates/voi_wasm/`, `scripts/build-wasm.sh`)
require a **strict semver increase** in `web/package.json`. CI enforces this via
`tests/test_studio_release_version.py`.

## Required imports

```tsx
import { Studio } from "@oliverevans96/blueberries-voi-studio";
import "@oliverevans96/blueberries-voi-studio/styles.css";
```

`Studio` is the full app shell (`StudioProvider` + layout). The exported
`<Studio />` component is **self-contained**: it creates its own mount root via
an internal `containerRef` and does **not** require a `#app` element in the host
document. For custom mount roots or split layouts, use `StudioProvider` with
`containerRef` and render `StudioLayout` inside a host element you control.

### Optional `blogPostUrl`

Override the title-bar “Read the blog post” link when embedding on a page that
should point at a different article:

```tsx
<Studio blogPostUrl="https://yoursite.example.com/posts/blueberries" />
```

The same prop is available on `StudioProvider`. When omitted, the link falls
back to the package default (`STUDIO_BLOG_POST_URL` in `studioLinks.ts`).

## Astro island (React 19, lazy)

Use `client:only="react"` and defer loading until the island is near the viewport:

```astro
---
// StudioIsland.astro
---
<div id="studio-slot" class="studio-slot" data-studio-lazy></div>

<script>
  const slot = document.querySelector("[data-studio-lazy]");
  if (!slot) throw new Error("studio slot missing");

  const observer = new IntersectionObserver(
    (entries) => {
      const hit = entries.find((e) => e.isIntersecting);
      if (!hit) return;
      observer.disconnect();
      void import("./StudioIsland.client");
    },
    { rootMargin: "200px" },
  );
  observer.observe(slot);
</script>
```

```tsx
// StudioIsland.client.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Studio } from "@oliverevans96/blueberries-voi-studio";
import "@oliverevans96/blueberries-voi-studio/styles.css";

const slot = document.querySelector("[data-studio-lazy]");
if (!slot) throw new Error("studio slot missing");

createRoot(slot).render(
  <StrictMode>
    <Studio />
  </StrictMode>,
);
```

Mount the client component with Astro’s island directive on a wrapper if you prefer
declarative lazy boundaries:

```astro
---
import StudioClient from "./StudioIsland.client.tsx";
---
<StudioClient client:only="react" />
```

Combine `client:only` with the `IntersectionObserver` pattern when the studio is
below the fold and you want to avoid loading WASM until scroll.

## Local smoke (workspace tarball)

```bash
./scripts/build-wasm.sh
cd web && npm run build:lib && npm pack
cd examples/embed && npm install && npm run build
```

The example under `web/examples/embed/` depends on `file:../..` for CI-friendly
smoke without a registry publish.

## Peer dependencies

Hosts must provide **React 19** and **React DOM 19** (`peerDependencies`). The
library bundles D3 and the WASM worker graph.

## Vite dev: `optimizeDeps.exclude`

When developing against a linked or `file:` tarball install, Vite's dependency
pre-bundling can hoist the studio package into `node_modules/.vite/deps` and
break the WASM worker graph or duplicate React peers. Exclude the package from
`optimizeDeps` in your host `vite.config.ts`:

```ts
import { defineConfig } from "vite";

export default defineConfig({
  optimizeDeps: {
    exclude: ["@oliverevans96/blueberries-voi-studio"],
  },
});
```

Restart the dev server after changing this setting. Production builds are
unaffected — this applies only to Vite's dev pre-bundle step.
