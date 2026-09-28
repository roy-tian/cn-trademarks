# AGENTS.md

Guidance for AI coding agents working in this repository.

## Commands

- No dependencies and no build step: Node runs the `.ts` files directly via type stripping (CI uses Node 24). Use only erasable TypeScript syntax (no `enum`, `namespace`, parameter properties) and import local modules with the `.ts` extension.
- Single test: `node --test --test-name-pattern="<name>" tests/snapshots.test.ts`
- `npm run generate:sql` regenerates `sql/postgresql/trademark_nice.sql` from `data/nice.jsonl`; `npm run generate:snapshots` regenerates `sql/postgresql/trademark_nice_snapshots.sql` from `data/snapshots/*.jsonl`.
- The Python pipeline (`scripts/*.py`) needs the source PDFs/ODS files linked in NOTICE.md, which are not in the repo. Run it from the repo root because it reads `data/...` by relative path.

## Data and generated SQL

- The SQL seeds are generated and committed. After any JSONL change, regenerate the matching SQL and commit both, because tests check the SQL against the JSONL. Never hand-edit generated SQL. `trademark_nice_fixes_v*.sql` is the exception: it is hand-written.
- Data files are 1–3 MB of JSONL, so use `grep`/`head` instead of reading them whole. Keep rows sorted by `code` and keep the existing line format, so diffs touch only the changed rows.
- Names are verbatim source text. Do not normalize punctuation across editions (NCL10-2016 uses half-width `(`/`;`/`,` where later editions use full-width). Keep trailing `*` cross-group markers. Synonyms for one code are joined with a full-width `，`.
- The first four digits of an item code are not necessarily its group. Always use `parentCode`.
- `version` / `source_year` means different things in each edition. Take the edition from the filename or the `edition` column.
- `data/*` and `sql/*` are exported by path (`package.json` `exports`), so renaming or moving files there is a breaking change.

## Corrections must survive regeneration

- Record every name or structure fix in the script that produces the file, not only in the JSONL:
  - legacy `data/nice.jsonl`: `OCR_FIXES` in `scripts/apply-revision.ts`
  - NCL10-2016: hard-coded fixes near the end of `scripts/extract-2016.py`
  - NCL11/12 C-items: `OCR_FIXES` in `scripts/extract-scanned.py`
  - snapshot assembly: `manual_group` and `ods2026_untrusted` in `scripts/build-snapshots.py`
- Pin each audited name in `tests/snapshots.test.ts` ("keeps audited OCR-sensitive names corrected").
- When the TIPO cross-strait ODS disagrees with the CN text, the CN text wins.
- `build-snapshots.py` reads `data/nice.jsonl` and `data/snapshots/ncl10-2016.jsonl` as inputs, so changes to those files flow into the NCL11–13 snapshots when they are regenerated.
- Legacy `data/nice.jsonl` / `trademark_nice.sql` exist for existing consumers. Never change their row count or codes; only fix names. Seeded databases never pick up INSERT changes, so a release that fixes names also ships idempotent `UPDATE`s in a new `sql/postgresql/trademark_nice_fixes_v<version>.sql`, with a README note.
- If per-edition class/group/item counts change, update the `expected` map in `tests/snapshots.test.ts`, the README table, and the count assert in `extract-2016.py` (for NCL10).
- The alias-view logic (split item names on `，`, keep only bracket-balanced fragments) is duplicated in both SQL generators and mirrored in both test files. Change all four together.

## Docs, git, release

- README.md and NOTICE.md are written in Chinese. Keep them in Chinese.
- Commit to `develop`, not `master`. CI (`.github/workflows/ci.yml`) runs only on pushes to `master` and on PRs.
- Use English Conventional Commits (`feat:`, `fix:`, `ci:`, `chore:`), with a bulleted body for non-trivial changes.
- Release: bump `version` in package.json, commit `chore: release vX.Y.Z`, then tag `vX.Y.Z`. Pushing the tag publishes to npm (OIDC trusted publishing) and creates the GitHub release. Publishing is skipped if the tag doesn't match the package version. Never tag or push unless asked.
