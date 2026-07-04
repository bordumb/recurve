"""AP-5 counterexample: the old propose — crashes on malformed JSON (uncaught JSONDecodeError) and reads a
non-zero exit as a silent {}. A misbehaving agent is fatal or invisible, never a typed AgentError."""

import json
import subprocess

from recurvelib.loop.adapters import CommandActor as _Real


class CommandActor(_Real):
    def propose(self, contract, item, evidence):
        payload = json.dumps({"contract": contract, "item": item, "evidence": str(evidence)})
        out = subprocess.run(self.cmd, input=payload, capture_output=True, text=True)  # BUG: ignores returncode
        text = out.stdout.strip()
        return json.loads(text) if text else {}                                        # BUG: unguarded parse
