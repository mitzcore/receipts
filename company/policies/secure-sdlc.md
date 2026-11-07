# Secure Development Lifecycle

- All changes go through a pull request with at least one approving review
  from a code owner (`.github/CODEOWNERS`). Direct pushes to `main` are blocked.
- CI runs tests and lint on every PR.
- Production deploys need approval from a second engineer (GitHub
  `production` environment).
- Production, staging and development are separate AWS accounts.
