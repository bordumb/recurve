"""BROKEN counterexample for TK-18: a resolver that leaves the agent EMPTY when
AGENT_CMD is unset. Downstream, the loop then stalls on the required $AGENT_CMD
(or launches nothing) — exactly the friction `recurve run` exists to remove."""


def resolve_agent(agent_flag, env_agent, default="claude -p --permission-mode bypassPermissions"):
    if agent_flag:
        return agent_flag, "flag"
    if env_agent:
        return env_agent, "env"
    return "", "default"
