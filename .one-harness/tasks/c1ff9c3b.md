## Question 1 (open): Should the code folder be `script/` or `scripts/`?

Teammates committed the SAT and CP code under `script/` (singular), while Task.md and the global project structure assign `scripts/`. The ILP code and the shared loader and checker still have to be created, so they need one agreed location. The folder name is also written into imports such as `from script.cp.cpSolver import CPSolver` in script/cp/runCP.py and script/cp/test_cp_workflow.py.

- **Rename to `scripts/`:** the code matches Task.md and the global structure, and the imports in script/cp/ are updated. Cost: one mechanical commit, and teammates must pull it before their next push, or their later work under `script/` conflicts with the rename.
- **Keep `script/`:** no code moves, and Task.md is changed to say `script/`. Cost: this project stays different from the global structure, and that exception must be recorded in AGENTS.md with its reason.

**Recommended option:** Rename to `scripts/`, because the team plan and the global structure already agree on that name and only one folder of imports must change.