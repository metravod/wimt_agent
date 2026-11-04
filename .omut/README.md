<!-- Tool file: `omut zero` rewrites it to the current version. Don't edit it by hand; put the project's own rules in AGENTS.md. -->
# Project meta

This directory holds the project's meta in the [omut](https://github.com/metravod/omut) format: why the project exists, what state it is in, what comes next, and why it is built the way it is. Agents keep it current as they work, so the next agent or person can pick the project up without digging through the code.

## Reading it

1. `brief.md`: why, what it is, where it runs, what works now, what comes next. At most 60 lines; start here.
2. `decisions.md`: one line per decision, with the reason. `open` and `doubted` ones wait for an answer.
3. `threads/`: unfinished work, each thread with its next step.
4. `log.md`: one line per session, newest first.

`local/` is not in git: each copy of the project keeps its own there (see "Two layers").

Reading needs nothing installed. If you are only reading, you don't write anything here.

## Keeping it

If you work on the project, keep the meta by the rules below. `omut check` checks their shape and freshness, but the rules work without the tool.

Headings, field names and labels stay as below: `check` looks for them. Write the text itself in the language the project's people use.

### Two layers

- **The project layer** (`brief.md`, `decisions.md`, `threads/`, `log.md`) goes into git and to everyone who clones the repository: why, what, decisions, the work, and the public footprint (the repository, releases, packages, public sites).
- **The instance layer** (`local/`) is the memory of this copy, like `.env`: this machine (the checkout, symlinks, installs, virtualenvs, agents' configs), servers and containers, cron, data and backups, where secrets are kept (never the values), how to deploy and roll back. `.omut/.gitignore` keeps it out of git.

The test for a fact: would a stranger who clones the repository need it, and is it true for them? If not, it goes to `local/`. `check` warns about home paths and IP addresses in the project layer.

**Private meta.** When git ignores the whole `.omut/` (`omut start --private` puts it into `.git/info/exclude`, for a repository that is not yours), both layers are this copy's: nothing here is committed, so don't `git add -f` it, and `check` doesn't look for leaks. The pointer for agents is `CLAUDE.local.md`, ignored as well; the repository's `AGENTS.md` stays as it is. Sort facts as if the meta were shared: it may be one day, and the test for a fact still works. "Why" is the project's intent as far as you can tell it; add why this copy is kept, which is often what matters here. To share the meta later, the human removes the omut lines from `.git/info/exclude`, runs `omut zero` and commits `.omut/`; move this copy's facts to `local/` first.

**Worktrees.** A clone keeps one memory, in its main checkout. `local/` is there, and so is private meta; a linked git worktree doesn't get its own, which would go when the worktree goes. Meta in git exists in each worktree and follows the branch. `omut hook start` gives the full path in a worktree; without the hook, find it with `git worktree list` (the first line is the main checkout).

### Files

**`brief.md`: the project's brief. Always read, at most 60 lines.**
Frontmatter: `status` (`active` | `frozen`), `updated` (when the text changed), `verified` (when "Where it lives" and "Now" were last checked against reality), `by` (`agent/model`, the tool that writes and its model, such as `claude-code/opus-5.5`), optional `adr` (the project's ADR directory).
Sections, all required:
- **Why**: the original intent, 1–3 lines. Never rewritten after the fact: a changed intent is a decision in `decisions.md`.
- **What it is**: how it works, 3–10 lines, for a human. Links to the project's key documents.
- **Where it lives**: the public footprint, with dates: the repository, releases, packages, public sites, external documents. This copy's machine and servers go to `local/instance.md`. Empty means it is published nowhere.
- **Now**: what works, what is broken. Lines `**Verified:**` (how) and `**Not verified:**`.
- **Next**: 3–7 items. Small ideas live here too.

**`decisions.md`: the decision registry.** One line per decision:
`- D7 [accepted 2026-09-10] What was decided, why, what was rejected → link`
Statuses: `open` (not decided, there are options; may say since when: `[open 2026-09-10]`), `accepted`, `doubted` (decided, but there is a doubt), `superseded → Dn`. If the project has ADRs (`adr:` in the brief), they are the registry for the decisions they record: don't copy them here; `decisions.md` holds the decisions without an ADR, and a line at its top says where the ADRs are. `check` reads an ADR's status from frontmatter, a `Status:` line or a `## Status` section: `proposed` or `draft` waits for the human like `open`, `Firmness: tentative` like `doubted`, no status counts as decided. A registry that already mirrors its ADRs may stay as it is; new ADRs are not copied. Without ADRs, the reason goes right into the line, 1–3 sentences; if it doesn't fit, that's a reason to write an ADR. Lines are never deleted; a decision changes through `superseded`. A neighbouring project's decision is a link: `→ ../<neighbour>/.omut/decisions.md`.

**`threads/<slug>.md`: a thread of work**, only for work on substance (ideas without work go to "Next"). At most 80 lines.
Frontmatter: `status` (`active` | `parked` | `done` | `dropped`), `updated`, `by`, and for `parked`, `parked_because`:
- `stamina`, `limits`: continue from the same spot;
- `doubt`: resolve the doubt first (often together with a `doubted` decision);
- `blocked`: waiting on something external;
- `priority`: deliberately put aside for something else;
- `unknown`: the reason was never recorded; only for threads reconstructed during adoption.

Body: `# Title`, then the lines `**Goal:**`, `**Where we got:**`, `**Verified:**` / `**Not verified:**`, `**Open:**`, `**Next step:**`.

**`local/instance.md`: this copy's memory.** Not in git. Frontmatter: `updated`, `by`. Sections: **Where it lives** (this machine, servers, containers, cron, data, backups, with dates), **Access** (where the secrets, tokens and accounts are kept, never the values), **Runbook** (deploy, roll back, restart, move). `local/log.md` is this copy's events in the log format: deployed, moved, rotated a token.

**Claims about reality.** Every `- ` line of "Where it lives" (in `brief.md` and `local/instance.md`) and of "Access" is a claim. Give it a way to check it and the date it was last checked:
`- skill adr: ~/.claude/skills/adr → this checkout · how: readlink ~/.claude/skills/adr · seen 2026-11-03`
`how` is a command or a place to look; omut never runs it, an agent does. `check` warns about a claim not seen for 30 days and counts the claims without `how`; at session start the agent is offered the claims seen longest ago. A value that changes faster than that (the latest release, a count, the state of a branch) doesn't belong in a claim: where one command gives the answer, write where to look, not the value.

**`log.md`: history, newest first.**
`- 2026-10-31 · claude-code/opus-5.5 · What was done; verified: how → link`
One or two lines per session, details by link to a thread or a decision. The author is `agent/model` or `human`. Past 50 entries, old ones move to `log-archive/<year>.md`.

### Rituals

- **Session start.** Read `brief.md`, the `active` and `parked` threads, the `open` and `doubted` decisions. If a thread says "Verified", rerun that check before continuing.
- **Checking a claim.** Run its `how` (ask the human first where it touches servers or anything outside this directory) and compare with the claim. It holds: set `seen` to today. It doesn't: tell the human and fix the line with them, never silently. Note in `local/log.md` what you saw, not just "checked".
- **Looking for the footprint** (adopting, moving, "is anything else running?"). Search for the project's path and name where footprints hide: agents' skills (`~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills`), MCP configs (`~/.claude.json`, `.mcp.json`, `~/.codex/config.toml`, `~/.cursor/mcp.json`), agents' settings and memory kept by path (`~/.claude/settings.json`, `~/.claude/projects/`), binaries and tool installs (`~/.local/bin`, `uv tool list`, `pipx list`, `brew list`, `npm ls -g`), services and schedules (`crontab -l`, `~/Library/LaunchAgents`, `systemctl --user list-units`), containers (`docker ps -a`, compose files), shell profiles (aliases, `PATH`). Anything found that is not written down goes to `local/instance.md`, or to the human.
- **A decision is made.** An ADR, if the project keeps them; a line in `decisions.md` otherwise.
- **A piece of work is done, or parked.** Update the thread (create it if there is none), "Now" in `brief.md`, a line in `log.md` (more work the same session extends that line); what changed in this copy only (a deploy, a move, an install) goes to `local/instance.md` and `local/log.md`. Do it before you tell the human the work is done, and before a commit: an agent doesn't see the session end, so waiting for it means never. The result must be checkable: what was done, what was verified and how, what was not verified, the next step.
- **Moving the project.** The meta moves with the directory; what breaks is outside it: symlinks into it, absolute paths in agents' settings and permission rules, virtualenvs, agents' memory kept by path, cron and services. Go through "Where it lives" in `local/instance.md`, search for the old path, fix what you can and show the human the rest; record the move there and in `local/log.md`.
- **Freezing.** A final "Now", a log line, check "Where it lives", then `omut freeze <project>`, only with the human's consent.

### Adopting a project

A project without meta (`omut start` creates the templates):
- **Look for history everywhere, not only in the code:** git, the project's documents and untracked files, old journals (`.drift/` and the like), agents' memory and sessions, neighbouring directories with a similar name, external documents. What only one agent's memory holds goes into the meta: other agents can't see it.
- **Don't invent "Why" or the reasons for decisions.** What the sources don't say, write as unknown ("not known, ask") and ask the human.
- **The log does not retell commits.** Entries reconstructed from sessions are fine: the author is whoever writes the line, the text starts with `(from session)`. Don't copy an old journal into `log.md`: if it stays, link to it in the first entry; if it is going away, move it as is to `log-archive/` (any file name; `check` doesn't read the archive) and link to that.
- **A date the sources don't give stays unknown.** A decision says so in its status: `[accepted ?]`. A log entry takes the latest date it can be pinned to and says `(date approximate)`; history with no dates at all goes to `log-archive/` as is.
- **A fork is a separate project.** Only accepted decisions carry over from the ancestor; goals, loose ends and footprints stay with it.
- **If the repository is public on GitHub,** offer the human the omut badge for `README.md`: `omut start` prints it, with a link to the CI recipe.
- **Agents' memory is the human's.** Once what only one agent's memory held is in the meta, the same facts live in two places and will drift. Don't change that memory on your own. Ask the human once: keep it as it is, or from now on keep only their preferences and what they asked to keep out of the meta? If they choose the second, add this line to the file with the omut block (`AGENTS.md`, or `CLAUDE.local.md` for private meta), outside the block, where `omut zero` leaves it: `Agents' memory holds only the human's preferences and what they asked to keep out of the meta; facts about the project go to .omut/, and memory links to them.`
- **Project rules belong in `AGENTS.md`.** If they live in one agent's file (`CLAUDE.md` and the like), offer the human to move them to `AGENTS.md` and make the vendor file a pointer (`ln -s AGENTS.md CLAUDE.md`).

### Working together

Several people and agents can keep one project's meta in parallel branches:
- Each piece of work has its own thread, kept by one agent or person at a time (`by`). Pick up someone else's thread only when it is `parked` or they hand it over.
- Log lines from parallel branches merge on their own: `.omut/.gitattributes` tells git to keep both sides' lines. After a merge, check that the newest are on top.
- `brief.md` and `decisions.md` conflict like code. Resolve by keeping both sides' facts. Two new decisions with the same number: the one merged later takes the next free number, and its links follow.
- Decisions belong to the humans. With more than one, the line says who accepted it (`… accepted by Anna`), and an `open` decision names whom it waits for.

### Don't

- Don't copy project artifacts (ADRs, plans, docs) into the meta; link to them.
- Don't fix a mismatch between the record and reality silently; show it to the human.
- Don't put this copy's facts into the project layer, and never secret values anywhere in the meta.
- If the repo is distributed (a skill, a package, a template), committed meta ships to its users: decide whether `.omut/` belongs in `.gitignore`.
