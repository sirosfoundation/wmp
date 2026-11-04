# WMP docs site (Jekyll)

This directory is the source for the site published to GitHub Pages at
<https://wmp.name/>. It's a plain Jekyll site with custom
layouts and SCSS — the previous `cayman` remote theme has been removed.

## How to deploy

1. Copy the **contents** of this folder into the repository's `/docs`
   directory (overwriting the previous `index.md`, `testing.md`,
   `_config.yml`, and Gemfile).
2. Copy `.github/workflows/pages.yml` into the repository's
   `.github/workflows/` directory. Delete any old Pages workflow.
3. In the repository settings, under **Pages → Build and deployment →
   Source**, choose **GitHub Actions** (not "Deploy from a branch").
4. Push to `main`. The workflow syncs `spec/*.md` into `docs/_specs/`
   and publishes the site.

## Local preview

```
cd docs
bundle install
bundle exec jekyll serve
```

Before running locally, mirror what the workflow does — copy the spec
files so they render:

```
mkdir -p _specs
cp ../spec/*.md _specs/
```

## Layout

- `_config.yml` — site config + the ordered spec and extension catalogs
  shown on the landing page.
- `_layouts/` — `default.html` (chrome), `home.html` (landing),
  `spec.html` (inline-rendered spec), `page.html` (fallback).
- `_includes/` — header, footer, and inline SVG marks.
- `assets/css/main.scss` — Siros-inspired palette, ported 1:1 from the
  React prototype.
- `index.md` — the landing page (uses `home` layout).
- `testing.md` — the interop testing guide.
- `_specs/` — populated by the workflow from `/spec/*.md`; do not commit.

Update the landing page catalogs in `_config.yml` under
`spec_catalog` and `extension_catalog` when specs are added or renamed.
