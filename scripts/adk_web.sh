#!/usr/bin/env bash
# The ADK web UI, set up to work through Cloud Shell's Web Preview.
#
#     bash scripts/adk_web.sh          # then open http://0.0.0.0:8000/dev-ui/?app=cymbal_ops from the terminal
#
# Why not plain `adk web agent`? ADK 2.7's web server guards against DNS rebinding: bound to 127.0.0.1, it refuses
# any request whose Host isn't localhost. Web Preview reaches it as https://8000-cs-….cloudshell.dev, so every
# request gets "403 Forbidden: host not allowed" and the page stays blank. So we bind to 0.0.0.0 (Cloud Shell's VM
# isn't reachable from outside; Web Preview is the only way in, and it requires your Google sign-in) and allow
# Cloud Shell's preview origins for CORS. Requests from any other origin are still refused.
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
exec adk web --host 0.0.0.0 --port "${PORT:-8000}" --allow_origins 'regex:https://.*\.cloudshell\.dev' "$@" agent
