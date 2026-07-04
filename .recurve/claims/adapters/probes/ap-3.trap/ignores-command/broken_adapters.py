"""AP-3 counterexample: CommandActor ignores the external command and returns a canned patch, so the loop is
no longer driven by the agent at all."""

from recurvelib.loop.adapters import CommandActor as _Real


class CommandActor(_Real):
    def propose(self, contract, item, evidence):
        return {"x": "ignored"}                       # BUG: never runs the command, never reads its output
