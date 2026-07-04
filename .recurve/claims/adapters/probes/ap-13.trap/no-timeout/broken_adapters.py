"""AP-13 counterexample: propose runs the command with no timeout, so a hanging agent wedges the loop."""
import json
import subprocess
from recurvelib.adapters import CommandActor as _R, AgentError, _jsonable
class CommandActor(_R):
    def propose(self, contract, item, evidence):
        payload = json.dumps({"contract": contract, "item": item, "evidence": evidence}, default=_jsonable)
        out = subprocess.run(self.cmd, input=payload, capture_output=True, text=True)  # BUG: no timeout
        if out.returncode != 0:
            raise AgentError(str(out.returncode))
        text = out.stdout.strip()
        return json.loads(text) if text else {}
