<!-- omut:start -->
## Project meta (omut)
`.omut/` holds this project's meta: why it exists, what state it is in, what comes next. To understand the project, read `.omut/brief.md` first, then the decisions in `.omut/decisions.md`.
If you work on the project, keep the meta:
- at the start of a session, read `.omut/brief.md`, the `open` and `doubted` decisions in `.omut/decisions.md` and the unfinished threads in `.omut/threads/`;
- when a piece of work is done, before you tell the human it is done, add a line to the top of `.omut/log.md` (`- YYYY-MM-DD · agent/model · what was done → link`), update "Now" in `.omut/brief.md`, and record unfinished work as a thread in `.omut/threads/`. You won't see the session end, so don't wait for it.
- facts true only for this copy (this machine, servers, where secrets are kept) go to `.omut/local/`, which stays out of git.
Full rules: `.omut/README.md`.
<!-- omut:end -->
