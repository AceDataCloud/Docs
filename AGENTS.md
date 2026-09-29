# AceDataCloud Docs

This is the Mintlify documentation site. Navigation and site configuration
live in `docs.json`; `mint dev` previews pages and `mint broken-links`
checks links.

## Content ownership

- `scripts/sync_from_platformbackend.py` generates OpenAPI specs and
  localized guides and MCP pages from PlatformBackend. Check
  `managed_paths()` and `SKIP_DOC_KEYS` in that script before editing:
  generated paths are replaced by the sync workflow. Change their source
  in PlatformBackend or the generator instead.
- Other pages, such as hand-authored quickstarts and concepts, can be
  edited here. Keep navigation in `docs.json` consistent with page moves
  and additions.
- Use real API responses for examples. Customer-facing copy must not
  disclose internal suppliers, supplier hosts, hidden upstream model
  names, or routing/resale details. Public model names are fine.

## Verify

For generated-content or navigation changes, run the relevant checks in
`.github/workflows/validate-sync.yml` and the site's link check. For a
small hand-authored page change, preview the affected page and check its
links. Do not run the publication sync merely to validate prose.
