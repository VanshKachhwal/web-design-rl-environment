FROM ubuntu:24.04

# A working directory for the agent to author its HTML/CSS in. The agent
# publishes its finished site to /logs/artifacts/ (see instruction.md).
WORKDIR /app
RUN mkdir -p /logs/artifacts

# The reference screenshots to replicate (one PNG per page), rendered at emit
# time into the agent-env build context. instruction.md points the agent here.
COPY reference /app/reference
