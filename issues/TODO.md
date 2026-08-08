# Deferred work

The authoritative backlog of deferred work for prose-craft lives as [GitHub issues](https://github.com/MistressFilth/prose-craft/issues). This file is a discovery surface — keep the index in sync with `gh issue list --state open`, but the issue body is the source of truth for each item.

Conventions:
- Each deferred item gets a GitHub issue with the originating PR's "Out of scope" list as the consolidated search target.
- An item is *deferred*, not *closed* — the issue stays open until the work is shipped or explicitly cancelled.
- A scheduled Plan reference (e.g. "P29") belongs in the issue body, not in this index.

## Currently open

| # | Title | Origin |
|---|-------|--------|
| [#25](https://github.com/MistressFilth/prose-craft/issues/25) | `feat(xdg): $XDG_CONFIG_DIRS lookup for shared configuration` | #23 |
| [#26](https://github.com/MistressFilth/prose-craft/issues/26) | `feat(cli): voice delete subcommand` | #23 |
| [#27](https://github.com/MistressFilth/prose-craft/issues/27) | `feat(voices): per-project voice roots discovered from CWD` | #23 |
| [#28](https://github.com/MistressFilth/prose-craft/issues/28) | `perf(voices): persistent on-disk voice index` | #23 |
| [#29](https://github.com/MistressFilth/prose-craft/issues/29) | `feat(security): voice pack signing and verification` | #23 |
| [#30](https://github.com/MistressFilth/prose-craft/issues/30) | `feat(voices): _lexicons/ and _never_lists/ shared-root support` | #23 (pre-existing) |
| [#31](https://github.com/MistressFilth/prose-craft/issues/31) | `fix(xdg): Windows ACL parity for the runtime directory` | #23 |

## Conventions for closing an item

When picking up a deferred item:

1. Open the linked issue and read the original rationale before re-scoping.
2. If the design has shifted, update the issue body *before* pushing the PR that addresses it.
3. Once the PR lands, close the issue with a `Closes #<n>` footer on the squashed commit.
4. Update this index by deleting the row — don't leave closed items here.

## Origin

This file was created when PR #23's "Out of scope" list mistakenly referenced `issues/TODO.md` as the tracking surface — the file did not exist. The seven items (#25–#31) have been re-homed as GitHub issues. Subsequent PRs that defer work should follow the same pattern: open an issue, link it from the PR body, and add a row here.
