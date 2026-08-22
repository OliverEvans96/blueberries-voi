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

### Immutable pin (optional)

Explicit semver tags `studio-v*` (not legacy Python `v*`) also trigger a release:

```json
{
  "dependencies": {
    "@oliverevans96/blueberries-voi-studio": "https://github.com/OliverEvans96/blueberries-voi/releases/download/studio-v0.1.0/oliverevans96-blueberries-voi-studio-0.1.0.tgz"
  }
}
```

## Required imports

```tsx
import { Studio } from "@oliverevans96/blueberries-voi-studio";
import "@oliverevans96/blueberries-voi-studio/styles.css";
```

`Studio` is the full app shell (`StudioProvider` + layout). For custom mount
roots, use `StudioProvider` with `containerRef` and render `StudioLayout` inside
a host element you control.

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
