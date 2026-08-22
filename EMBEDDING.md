# Embedding the Blueberry Studio

The browser studio ships as **`@oliverevans96/blueberries-voi-studio`**, a React 19
library with scoped CSS under `.bv-studio` (T-142/T-143). WASM runs in a bundled
module worker (T-144).

## Install from a GitHub release

Studio releases are tagged `studio-v*` (not the legacy Python `v*` wheel tags).
After a maintainer copies `packaging/github-workflows/release-studio.yml` into
`.github/workflows/` and pushes a tag, download the `.tgz` from the release assets
or reference it directly:

```json
{
  "dependencies": {
    "@oliverevans96/blueberries-voi-studio": "https://github.com/oliverevans96/blueberries-voi/releases/download/studio-v0.1.0/oliverevans96-blueberries-voi-studio-0.1.0.tgz"
  }
}
```

Replace `studio-v0.1.0` and the filename with the tag and `npm pack` output from
that release.

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
