# AceDataCloud Docs

Mintlify documentation for AceDataCloud. Preview with `mint dev`; check public
links with `mint broken-links`. Navigation and site settings live in `docs.json`.

## Sources and ownership

- PlatformBackend owns Markdown source files and OpenAPI definitions. Edit the
  source, not generated Docs pages.
- The read-only `/api/v1/documents/publication/?lang=en` backend endpoint exports
  public documents by stable source key, including standalone guides and MCP.
  It includes exact-locale content, source SHA-256, and translation readiness.
  Display-oriented API/sibling relations are not a publication contract.
- Every configured locale's `guides/` and `mcp/` directories are generated.
  Existing Greek, Finnish and Serbian directories are also reconciled because
  their unlisted URLs remain accessible, without adding them to the language menu.
  `mcp/overview.mdx` is explicitly hand-authored and preserved. Public source
  records without an old service route use `guides/platform/<source-key>.mdx`.
  Existing routes and the exact Coding route map are preserved.
- `openapi/` contains specs for APIs with public platform document records;
  private markers and temporary publication holds are still enforced.
- Generated navigation is reconciled atomically with pages: Coding translations,
  additional public guides, MCP pages, and OpenAPI groups become discoverable;
  retired generated links are removed. Existing editorial groups are preserved.
- Quickstarts, concepts, pricing, FAQ, and other editorial pages are maintained
  here. They are not automatically rewritten from API changes.

## Synchronization contract

`Sync Ecosystem Contracts` is the only source-change trigger. The Docs workflow
serializes all writers, checks out current `main` after acquiring the queue, and
validates that an event SHA belongs to the current backend history. Old events
cannot republish old source snapshots. A final source check rejects a backend
revision that advanced during generation; normal Git push rejects concurrent
editorial changes without overwriting them.

Hourly reconciliation picks up asynchronous source deployment and translation
completion even when no new Git event occurs. Before switching this consumer on,
deploy the backend publication endpoint; unavailable or malformed feeds fail
closed and do not fall back to the old display API.

For every generated page, the database source hash must match the checked-out
Markdown and the target translation must be current. Catalog identity must also
remain consistent across locale reads. There is no automatic language fallback.
When a translation is pending, an existing page is retained for availability but
is explicitly reported as incomplete; a missing page is not fabricated. Ready
pages and public withdrawals can still publish. Exit status **2** means partial
publication and fails the workflow's final completeness gate. Other nonzero
statuses abort publication; **0** means every expected page is current.

The workflow retains `docs-sync-report` for 14 days and puts pending page keys,
locales, and reasons in the job summary. Generated output is staged and validated
before an atomic publish; interruption recovery includes navigation and all MCP
locales. A separate MDX compilation gate parses all generated pages before Git
push. Plain Markdown braces are escaped outside code rather than interpreted as
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
from the same publication exporter for reproducible, offline verification. Reports
belong outside the generated output tree. No sync command writes the backend DB
or generates translations.
