"""AP-17 counterexample: propose catches only TimeoutExpired, so a command that cannot be run leaks a raw
FileNotFoundError."""
import json
import subprocess
from recurvelib.loop.adapters import CommandActor as _R, AgentError, _jsonable
class CommandActor(_R):
    def propose(self, contract, item, evidence):
        payload = json.dumps({"contract": contract, "item": item, "evidence": evidence}, default=_jsonable)
        try:
            out = subprocess.run(self.cmd, input=payload, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:     # BUG: FileNotFoundError not caught
            raise AgentError("timed out") from e
        if out.returncode != 0:
            raise AgentError("nonzero")
        text = out.stdout.strip()
        return json.loads(text) if text else {}
