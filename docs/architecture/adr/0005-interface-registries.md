# ADR 0005: Interface Registries and Compatibility Facades

Status: Accepted in v12.18.

## Decision

CLI commands are registered through `CommandSpec`, HTTP routes are inventoried
through `RouteSpec`, and Studio assets are loaded with `importlib.resources`.
The historical `song_agent.cli`, `song_agent.server`, and `song_agent.webui`
modules remain compatibility facades only.

Command and HTTP implementations are grouped by bounded context. Public command
names, arguments, output, exit codes, HTTP paths, payloads, and status codes are
protected by snapshots and the existing contract suites.

## Consequences

New commands and route metadata must be registered in a bounded-context module.
The compatibility facades cannot contain business branches. Static Studio
markup, CSS, and JavaScript are package resources rather than Python literals.
The legacy route bodies remain behavior-compatible while application-service
extraction continues; no new route may add direct private-file mutation.
