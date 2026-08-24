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

CI builds the docs site in the `docs` job and uploads `docs-dist`; the `deploy`
job re-publishes it on green `main` pushes.
