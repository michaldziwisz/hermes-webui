# Evidence for PR #7258 (accessibility fixes)

Screenshot evidence lives on this branch instead of in the PR, because the
repository's `.gitignore` deliberately excludes generated screenshots
(`screenshot-*.png`, `full-UI.png`, `docs/*` except `*.md`).

## before-after/

Same conversation, same isolated `HERMES_HOME` and `HERMES_WEBUI_STATE_DIR`.
`transcript-master.png` is upstream master; `transcript-branch.png` is the PR
branch.

They are visually identical, which is the expected result: these commits change
the accessibility semantics (roles, accessible names, heading structure), not the
visual layout. The images prove nothing regressed visually. The proof that the
change works is the accessibility tree diff in the PR description.

Captured over CDP `Page.captureScreenshot` at 1600x1000, full page.
