# My Self-Learning Bot

This directory is an intentionally isolated project module inside the AutoAssistantWorkerBot repository.

## Boundary

- The module owns its own frontend and future bot logic.
- It does not reuse the existing `scripts/`, `input/`, or `memory/` runtime files.
- The existing AutoAssistantWorkerBot only provides a navigation entry point to this module.
- Persistent bot knowledge/memory is planned to live in a GitHub Gist as `brain.json`, subject to a separate security and access design before implementation.

## Current status

Scaffold only. Functional bot features will be added after the project specification and architecture are finalized.
