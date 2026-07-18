# Contributing

Thank you for contributing to MediaHub. This document defines the workflow
every contribution must follow.

## Code of conduct

Be professional and respectful. Personal attacks, harassment, and
discrimination are not tolerated.

## Before you start

- Open or claim an issue. Large changes should be discussed first.
- Confirm your idea fits the architecture in `docs/ARCHITECTURE.md`.
- Phase-scoped work must respect the phase roadmap; do not leap ahead.

## Branching model

```
main
 └── feature/<phase>-<topic>   # e.g. feature/2-youtube-provider
 └── fix/<topic>
 └── release/vX.Y.Z
```

- Branch from `main`, rebase before merging.
- Squash-merge PRs; one concern per PR.

## Commit messages

Conventional Commits, scoped per layer:

```
<type>(<scope>): <imperative summary>

<body explaining why, not what>

<footer: BREAKING CHANGE:, refs #issue>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`,
`ci`, `style`.

Scopes: `flutter`, `android`, `engine`, `docs`, `ci`, `deps`.

Examples:

```
feat(engine): add youtube provider with metadata extraction
fix(android): stop foreground service on task completion
docs: expand bridge contract for progress events
```

## Pull request checklist

- [ ] Branch is up to date with `main`.
- [ ] `flutter analyze` is clean.
- [ ] `ruff check python_engine` is clean.
- [ ] `flutter test` passes.
- [ ] `pytest -q` (in `python_engine`) passes.
- [ ] New code is covered by tests.
- [ ] Public API changes are documented.
- [ ] Commit messages follow Conventional Commits.
- [ ] No secrets, keys, or personal data committed.

## Code style

- **Dart**: `analysis_options.yaml` (strict). Prefer `final`, `const`,
  single quotes, trailing commas.
- **Kotlin**: ktlint + detekt. 4-space indent, 120-col limit.
- **Python**: ruff (line length 100). Type hints required on public APIs.

## Architecture conformance

- Do **not** bypass the bridge. Flutter must not call Python directly; it goes
  through the method channel → Kotlin → JSON-RPC.
- Do **not** hardcode platform logic in `DownloadManager`. New platforms are
  added as provider modules only.
- Keep the dependency rule: `presentation → domain ← data`.

## Testing expectations

| Layer | Required |
|-------|----------|
| Flutter | unit + widget test for every new screen/notifier |
| Python | unit test for every new provider + engine method |
| Android | service/bridge test for new method-channel handlers |

## Review process

1. Automated CI must be green.
2. One maintainer review for `feat`/`fix`; two for architectural changes.
3. Reviews focus on architecture conformance, testability, and security.

## Release process

- Maintainer bumps version in `pubspec.yaml`, `mediahub_engine/__init__.py`,
  and `CHANGELOG.md`.
- Tag `vX.Y.Z` on `main`.
- Release build produced per `docs/BUILD.md`.
