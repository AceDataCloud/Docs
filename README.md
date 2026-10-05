# AceDataCloud Docs

Mintlify documentation for AceDataCloud. Preview with `mint dev`; check public
links with `mint broken-links`. Navigation and site settings live in `docs.json`.

## Sources and ownership

- PlatformBackend owns Markdown source files and OpenAPI definitions. Edit the
  source, not generated Docs pages.
- Reuse the existing `/api/v1/documents/?lang=en` list, including normal
  pagination. Its additive `content_source` metadata identifies the source file,
  source SHA-256, exact-language readiness and content hash. Independent Text
  guides and MCP pages are read directly rather than inferred from API siblings.
  No new endpoint, response envelope or export mode is required.
- Every configured locale's `guides/` and `mcp/` directories are generated.
  Existing Greek, Finnish and Serbian directories are also reconciled because
  their unlisted URLs remain accessible, without adding them to the language menu.
  `mcp/overview.mdx` is explicitly hand-authored and preserved. Public source
  records without an old service route use `guides/platform/<source-key>.mdx`.
  Existing routes and the exact Coding route map are preserved.
- Per-locale API reference indexes are generated from the published specs.
  Source-file links are resolved to the correct locale route; platform-relative
  document links are made absolute instead of being interpreted as Docs routes.
- `openapi/` contains specs for APIs with public platform document records;
  private markers and temporary publication holds are still enforced.
- Generated navigation is reconciled atomically with pages: Coding translations,
  additional public guides, MCP pages, and OpenAPI groups become discoverable;
  retired generated links are removed. Existing editorial groups are preserved.
- Quickstarts, concepts, pricing, FAQ, and other editorial pages are maintained
  here. They are not automatically rewritten from API changes.

## Synchronization contract

PlatformBackend's daily ecosystem CronJob is the only publication coordinator.
It checks out a pinned current Backend source, runs this repository's existing
generator, validates MDX, and opens or updates a PR. Mintlify publishes after
normal review and merge. No cross-repository dispatch or hourly GitHub writer
remains. Every daily pass also checks translation completion without requiring
a new source commit.

For every generated page, the database source hash must match the checked-out
Markdown and the target translation must be current. Catalog identity must also
remain consistent across locale reads. The normal list keeps its display fallback; the Docs consumer checks metadata
and never counts that fallback as a current translation.
When a translation is pending, an existing page is retained for availability but
is explicitly reported as incomplete; a missing page is not fabricated. Ready
pages and public withdrawals can still publish. Exit status **2** means partial
publication and prevents the daily controller from advancing its checkpoint. Other nonzero
statuses abort publication; **0** means every expected page is current.

The generator writes a completeness report for the controller; incomplete
publication is retried on the next daily run. Generated output is staged and validated
before an atomic publish; interruption recovery includes navigation and all MCP
locales. A separate MDX and local-link gate checks every site page before Git
push, including editorial entry points. Plain Markdown braces are escaped outside code rather than interpreted as
JavaScript expressions. Customer example sanitization remains mandatory.

## Verification

```sh
python -m compileall -q scripts tests
python -m unittest
npm ci --ignore-scripts
node --test tests/mdx-validation.test.mjs
node scripts/validate_mdx.mjs /path/to/generated-preview
mint broken-links
```

For read-only reconciliation, run:

```sh
python scripts/sync_from_platformbackend.py --backend-dir ../PlatformBackend \
  --output-dir . --dry-run --report /tmp/docs-sync-report.json
```

`--preview-dir /tmp/docs-preview` preserves dry-run output in a new directory for
review and link checking. Set `PUBLIC_EXAMPLE_DENYLIST` and `--require-denylist` to
include private-value checks in a dry run; without it the report explicitly marks
that check unverified. Actual publication always requires the configured denylist.

`--catalog-dir /path/to/snapshots` loads files named `zh-cn.json`, `en.json`, etc.
containing complete responses from the same document list for reproducible,
offline verification. Reports
belong outside the generated output tree. No sync command writes the backend DB
or generates translations.

## Daily capability updates

PlatformBackend `scripts/sync_ecosystem.py` is the only scheduled coordinator.
One daily Kubernetes Job reviews Backend docs and API changes with Claude Code,
updates existing files, and creates or updates one reviewable PR per repository.
It never merges PRs or duplicates the Backend guide tree. Normal CI and review
remain required; publication and sub-repository mirroring run after merge.
