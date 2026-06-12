# Quality constitution — stable preset

For mature targets with external consumers. Same spine as pre-launch, two
rules replaced; human-owned — the loop obeys, never edits.

1. **Parse, don't validate.**
2. **Ports and adapters at I/O edges.**
3. **One source of truth.**
4. **Deprecate, don't delete.** Divergent paths get a deprecation marker, a
   migration note, and a removal gap filed with its own probe — external
   consumers get a window, not a surprise. (The pre-launch knife is wrong
   here: a removed public surface is someone else's outage.)
5. **Discovered problems become filed gaps** — never TODOs, never smuggled
   fixes.
6. **No fake green.**
7. **Consumers of a changed type are part of your change** — including a
   compatibility note when the consumer is outside this repo.
8. Build, lint, tests clean; no new suppressions, and touching a file with
   old suppressions files a gap to remove them.
