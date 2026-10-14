# Contributing

1. Open an issue describing the change.
2. Branch from `main` (`feat/…`, `fix/…`, `docs/…`).
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/) (`feat(api): …`).
4. Make sure `make check` passes: lint, type checks and tests for both apps.
5. Open a pull request that references the issue (`Closes #12`).

Architecture decisions live in [`docs/adr`](docs/adr). If a change affects the architecture, add a new ADR.
