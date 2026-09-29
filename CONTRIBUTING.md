# Contributing

Use this guide to take one ticket from local work to the shared development website. No AI tools are required. Start by [running the project](README.md#run-locally).

The official repository is [senior-design-organization/knights-sat-sim](https://github.com/senior-design-organization/knights-sat-sim). Keep its visibility unchanged. Build tickets live in [Jira](https://seniordesign-g20.atlassian.net/jira/software/projects/KSAT/boards/1), not GitHub Issues.

## The whole process

**Choose a Ready ticket → create a branch → build and test locally → open a pull request → pass checks and review → merge → verify deployment → mark Done.**

| Term | Meaning here |
| --- | --- |
| Ticket | One small piece of work with an owner and checks for completion. |
| Branch | Your line of work, separate from the shared `main` branch. |
| Commit | A named checkpoint of your changes in Git. |
| Pull request (PR) | A proposed branch change, with a diff, discussion, and automated checks. |
| CI | GitHub's automated tests and builds for a commit. Green means the configured checks passed. |
| Deploy | Replace the running website with a tested build. A merge and a deploy are separate steps. |

## Planning and board

| Jira status | Use it when |
| --- | --- |
| Backlog | The work is planned but has not been selected, or a prerequisite is unfinished. |
| Ready | The task is clear, its checks are practical, and its real prerequisites are available. |
| In Progress | Its owner is actively working on it. Start with one implementation ticket per person. |
| Review | The PR and test evidence are ready for review. |
| Done | The acceptance checks, merge/review rules, and applicable delivery check below are satisfied. |

Keep one accountable assignee. Flag blocked tickets, link the actual prerequisite using **is blocked by**, and explain what is missing. A Player's lesson unlock order is not necessarily developer build order: an isolated test fixture can stand in for an earlier completed lesson when the spec permits it.

Use the four epics to group foundation, Workspace, Challenges, and hosting. An epic is a group of tickets, not one person's task. Area labels such as `ui`, `server`, `sim`, `hosting`, and `docs` help find work. Select a small weekly goal and show working results at the end; fixed sprints and story points are not required.

## Before writing code

1. Pick an assigned **Ready** ticket and move it to **In Progress**. Read its goal, starting files, handoffs, and acceptance checks.
2. Read the linked spec sections. A spec is the shared agreement about behavior; the ticket is one piece of that implementation. Ask the owning teammate if they disagree. Record agreed changes in that spec.
3. Agree on any shared interface before coding both sides: route, request/response fields, errors, and who edits it. Backend schemas own API types; frontend code uses generated types.
4. Keep the task small enough for a few work sessions. Name the neighboring ticket that owns the next feature. Do not expand your task to implement a teammate's work.

Branches separate changes; they do not prevent two people from building the same feature or editing the same shared file. Coordinate changes to `server/api/main.py`, shared schemas, `ui/src/App.tsx`, shared UI controls, dependency files, and CI with the relevant owner. The [role table](docs/specs/project-plan.md#who-owns-what) gives a starting contact; Jira holds the current assignee.

## Branch and pull request

In a terminal at the repository root, first run `git status`. If you have existing changes, finish or preserve them before switching branches. Do not discard unfamiliar changes or use `reset --hard` to make this guide work.

With a clean working folder:

```bash
git switch main
git pull --ff-only
git switch -c codex/KSAT-10-packet-crc
```

Replace `KSAT-10-packet-crc` with **your exact Jira key** and a short description. The `codex/` prefix is just our branch convention; humans use it too. `--ff-only` stops instead of silently merging diverged history. If it stops, ask for help with the reported divergence.

Work locally and run the [checks for your area](docs/development.md#tests-and-lint). Inspect what you changed before committing:

```bash
git status
git diff
git add path/to/changed-file
git commit -m "KSAT-10 Add CRC-16 helper"
git push -u origin codex/KSAT-10-packet-crc
```

Replace the example path with your changed file(s), and use your own ticket key/message. Stage only your work. Never commit passwords, API tokens, `.env` secrets, or private SSH keys.

Open the repository on GitHub and choose **Compare & pull request**. Set the base to `main`; title it `KSAT-10 Add CRC-16 helper` using your key. Fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md), link the PR in Jira, and move the ticket to **Review**. A draft PR is fine for early help.

### Review and merge

- For ordinary contributors, ask one teammate other than the author to review and approve. Choose them when ready; tickets do not prescribe a fixed reviewer.
- **Diab may merge his own work without teammate approval after required checks pass.** Keep the PR, Jira link, and evidence. This exception does not apply to everyone and does not waive checks.
- Resolve failed checks and review feedback. If `main` changed or GitHub reports a conflict, update your branch and resolve each file with its owner; do not blindly choose all of one side. Recheck the combined result.
- Merge the PR into `main` through GitHub. Do not push implementation directly to `main` or force-push it. KSAT-41 owns GitHub enforcement; this rule applies even before enforcement is configured.
- After merge, delete the completed remote branch when no longer needed. For the next ticket, start again from updated `main`.

## Updating the shared website

A merge starts this chain in [GitHub Actions](https://github.com/senior-design-organization/knights-sat-sim/actions):

1. **CI** checks the new `main` commit and publishes its tested images.
2. **Automatically update development website** requests the update.
3. **Update website** installs it and checks the running revision and health.

Check the third workflow, not just the dispatcher. Its `DEPLOYED: <SHA>` line identifies the installed commit. SHA means the full Git commit identifier. For a visible feature, sign in to the [development site](https://knightsat.radio-ranger.com), check `/revision`, and repeat the ticket's relevant browser check. Newer merges can supersede an intermediate pending deployment; verify a deployed descendant contains your change if that happens.

This is internal testing. Updates can interrupt sessions, programs, and unsaved work, so save or download work before an update. Production session continuity is later work. A PR build never deploys. If deployment fails, record the failed run and ask Diab to investigate; do not change server credentials or delete storage to fix it.

## Definition of done

- The ticket's observable acceptance checks pass, including its relevant failure cases.
- New behavior has useful tests; docs-only changes have been checked for accuracy and links.
- The PR names the Jira ticket, explains the result, and records commands/manual checks with outcomes.
- CI and the review rules above are satisfied, and the PR is merged.
- For website changes, the deployment is confirmed and the relevant hosted behavior checked. Infrastructure-only work verifies its stated boundary; KSAT-26 owns the complete hosted learner journey.

Record evidence in the ticket and move it to **Done**. Do not claim a real integration passed because a test double or placeholder worked.

For external setup with no repository change, record the result and have another teammate verify it. A code PR/CI run is needed only if code or configuration changes. Keep secrets out of tickets.

## Ticket format

Use a deliverable title, such as **UI: Show the Challenge list**, and these short sections:

1. **Goal:** what someone can do after this ticket.
2. **Start here:** prerequisite tickets, real starting files, and the first small checkpoint. Label files that need to be created.
3. **Build:** ordered steps and the contract details needed for this slice.
4. **Check it:** action → expected result, including errors that matter.
5. **Handoff and references:** who owns adjacent work and exact spec links.

Keep assignee, status, epic, and blocking relationships in Jira fields. Keep required authorization, cleanup, error handling, and tests with the behavior they protect. Split independent features instead of leaving a large “finish everything” ticket.

## Specs and language

Use the [project plan](docs/specs/project-plan.md), [documentation map](docs/README.md), and [glossary](docs/glossary.md). Record decisions in the spec that owns them; do not add separate decision-record files (ADRs) or copy entire specs into tickets. Research is supporting material, not extra MVP scope.

If you choose to use AI, the same workflow applies. You are responsible for understanding the code, verifying it against the spec, and showing its behavior. AI output and generated tests are not evidence by themselves. Nobody needs an AI subscription or agent setup to follow this guide.
