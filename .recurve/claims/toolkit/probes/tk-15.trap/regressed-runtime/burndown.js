// Known-bad burndown.js: the FR-E regression. It stamps a wall-clock RUN_ID
// (the sandbox forbids Date.now() — it breaks resume) and tells the agent to
// read a cwd-relative `.recurve/RUN.md` instead of `${ROOT}/.recurve/RUN.md`.
// TK-15's probe MUST go RED against it.
const ROOT = '/tmp/probe'
const RUN_ID = (args && args.runId) || ('burndown-' + Date.now())

phase('Burndown')
const result = await agent(
  `You are running ONE improvement cycle. Read \`.recurve/RUN.md\` and obey it.`,
  { schema: { type: 'object' } }
)
return { runId: RUN_ID, result }
