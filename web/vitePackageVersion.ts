import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/** Read `version` from `web/package.json` for Vite `define` injection. */
export function readWebPackageVersion(): string {
  const webRoot = fileURLToPath(new URL(".", import.meta.url));
  const pkg = JSON.parse(
    readFileSync(join(webRoot, "package.json"), "utf8"),
  ) as { version: string };
  return pkg.version;
}
