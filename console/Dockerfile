# The flight dynamics console: one process with the simulator, the watcher and the agent (ADK, in-process).
# console/deploy.sh copies this next to agent/ and console/ in a temporary folder and builds it there.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY agent/cymbal_ops/requirements.txt agent-requirements.txt
COPY console/requirements.txt console-requirements.txt
ARG ADK_VERSION=2.7.0
RUN pip install "google-adk[mcp]==${ADK_VERSION}" -r agent-requirements.txt -r console-requirements.txt
COPY . .
# ONE worker: the clock, the watcher and the agent's session live in this process.
CMD exec uvicorn console.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
