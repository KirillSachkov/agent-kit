---
name: setup-harness
description: "Set up or update a project's Agent Kit workflow, rules and pinned skills."
disable-model-invocation: true
---

Configure the target repository. Ask one unresolved question at a time, with the recommended
answer first. Reuse decisions the owner already made. Start implementation only under the
resulting project rules.

1. **Inspect.** Resolve the target Git root, existing instructions, tracker, checks, delivery
   rules and skill manifest. Find the Agent Kit checkout and the full commit SHA to install.
   Reuse the project's pin when it provides the agreed workflow. Read
   `templates/project/AGENTS.md` and `docs/first-project.en.md` from the chosen revision.
   If the manifest uses source links, follow its source bootstrap for skill changes. Apply
   only project rules that match the resulting client metadata and installed skills.
2. **Choose.** Resolve the starter fields in order. Read facts such as CI names and test
   commands from the repository. Ask about decisions the files cannot settle.
   - **Instructions and tracker:** project language and where to record work.
   - **Start:** default to the owner explicitly choosing `implement` or `implement-spec`.
     If the owner opts in to implicit selection, write the ordinary-assignment start rule.
     An explicit assignment still authorizes the work.
   - **Work:** checkout or worktree, base selection and authority to clean up.
   - **Checks and evidence:** commands, required CI, test data and evidence location.
   - **Delivery:** destination, who accepts and who may publish, merge or deploy.
   - **Owner attention:** default to disabled. If enabled, agree on conditions and what each
     outcome authorizes. Use the pinned `templates/project/docs/agents/owner-attention.md`.
     General merge permission belongs under Delivery.
   - **Skills and clients:** offer the first-project guide's starter bundle and client
     selection in a fresh project. In an existing project, keep the current selections and
     client settings unless the owner asks to change them. Include the skills that the new
     instructions depend on.
3. **Preview.** Fill in the starter for a new repository. In an existing repository, update
   the agreed settings in place and preserve unrelated instructions. Show the proposed
   `AGENTS.md` changes and the skill selection at its full SHA. Use `tools/skills.py select`
   without `--apply` first. Set `--implementation-invocation manual` or `implicit` on the
   selection of `implement` and `implement-spec` to match the Start rule. Select
   `owner-attention` when enabled.
4. **Apply and check.** Once the owner approves the setup, apply the selection, preview the
   installation and resolve conflicts before installing. Adopt exact unmanaged copies using
   the distribution guide. If a conflict blocks setup, report any selection already written
   and the remaining conflict. After a successful install and check, write the agreed project
   rules and, when enabled, the classifier conditions. Verify that the instructions, the
   installed invocation settings and the selected classifier agree. Report the changed
   files, pin and check result.
