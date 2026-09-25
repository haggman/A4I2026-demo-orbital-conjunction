# agent/

**Unlike the five challenges, this folder will hold the complete working solution**—that is the point of a
demo. It is built in Stage 3.

What it will be: an ADK agent that reads the `a4i_orbit` tables through a Google-managed MCP server, holds
the operator's judgment in a tool of our own, and runs orbital what-ifs—*"what if we burn 0.4 m/s
prograde on Wednesday?"*—as code in an **Agent Runtime code execution sandbox**, through ADK's
`AgentEngineSandboxCodeExecutor`. Its output is a **Conjunction Assessment & Maneuver Recommendation**:
which object, when, how close, the risk under stated assumptions, what a manoeuvre costs, and what we are
assuming.
