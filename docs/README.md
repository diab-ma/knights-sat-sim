# Documentation map

You do not need to read every document before starting. Follow the first three rows, then open the specification linked by your ticket. The [MVP statement](specs/project-plan.md#mvp-what-done-means) says what is required and what is a stretch goal. **Required behavior** lives in specifications; **current work/status** lives in Jira; **historical evidence** records only what was checked on its date.

| What you need | Read |
| --- | --- |
| Run the project and know what currently works | [README](../README.md) |
| Take a ticket through Git, tests, PR, and deployment | [Contributing](../CONTRIBUTING.md) |
| Understand the product, parts, and team responsibilities | [Project plan](specs/project-plan.md) |
| Look up an unfamiliar word | [Glossary](glossary.md) |
| Run native tools or tests | [Development guide](development.md) |
| Build common browser controls or state handling | [Frontend](specs/frontend.md) |
| Implement APIs, sessions, simulation, or saved progress | [Backend and simulation](specs/backend-and-simulation.md) |
| Build terminal, editor, files, or cleanup | [Workspace](specs/terminal-workspace.md) |
| Implement packet encoding/decoding | [Packet format](specs/packet-format-v1.md) |
| Build Ready or Catch tasks and evidence checks | [Ground-station training](specs/ground-station-training.md) |
| Build the supplied PING activity | [Hello, Satellite!](specs/challenges/01-hello-satellite.md) |
| Check whether something was deliberately left out of the MVP | [Later hardening](specs/later-hardening.md) |

## How to read a technical specification

1. Read its short introduction and the section linked by your ticket.
2. Find the inputs, expected outputs, and failure behavior. A **contract** is that agreement between two parts of the program.
3. Use the examples and acceptance checks to decide what to test. “Must” and “use” describe requirements to implement, not proof that code exists.
4. Ask the owner of the neighboring ticket before changing a shared contract. Update the owning spec with the agreed answer.

For example, `POST /api/session` means “send an HTTP POST request to this path.” The adjacent table gives the JSON fields and response. A name such as `Session` refers to the record defined in that same document, not a library you must find online.

Tests may use a **fixture**: known sample data that lets one feature be built independently. A fixture does not prove the complete browser-to-server flow works. Final acceptance uses the real connected parts.

## Background reading: optional for the software MVP

- [Prior art](research/prior-art.md): earlier projects and design references.
- [Simulator trade study](research/simulator-trade-study.md): why we build our own small simulator instead of NOS3, COSMOS or Yamcs.
- [CCSDS and Direwolf](research/ccsds-space-packet-and-direwolf-path.md): detailed packet/radio research. The shorter Packet format spec is the implementation authority.
- [RF bench attenuation](research/rf-bench-attenuation.md): future physical radio work; not needed to run or build the software demo.
- [Part 97 research](research/part-97-rules.md): regulatory research for later radio work, not authorization to transmit.

Some research cites files on Diab's own computer. Those are provenance, not required setup steps. All required MVP contracts are in this repository. Ask Diab to share a source before relying on an unpublished file; do not assume another student's computer has the same path.
