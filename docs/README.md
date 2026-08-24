# Blueberries VOI documentation site

VitePress user docs for the freshness / VOI model. Published at
[oliverevans.dev/docs/blueberries/](https://oliverevans.dev/docs/blueberries/).

## Local development

```bash
cd docs
npm ci
npm run docs:dev    # http://127.0.0.1:5174
```

## Production build

```bash
cd docs
npm ci
npm run docs:build  # output in .vitepress/dist/
npm run docs:preview
```

CI uploads `docs/.vitepress/dist/` as the `docs-dist` artifact on green `main` pushes.
