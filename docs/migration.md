# Public source consolidation

Agent Kit combines the public source histories of `KirillSachkov/agent-harness` and `KirillSachkov/agent-clarity`. It does not import private home repositories, service accounts or project data.

## Preserved sources

| Source | Original main |
| --- | --- |
| Agent Harness | `5e051a49287724bff80a2568d73512d9b334d692` |
| Agent Clarity | `a8b3f408ab5373667680b3622048eecfdf41c47f` |

Both main histories are parents of the consolidated history. Named branches retain the other Agent Harness work:

- `history/agent-harness/draft/domain-design-kit`, original `8ca732395375415001900f8a0d9521919651bd4a`.
- `history/agent-harness/research/agents-md-practices`, original `ce4bb51d77e645b6c445ad5d31f14ec09d14316c`.
- `history/agent-harness/main` and `history/agent-clarity/main` retain the original main heads.

These branches preserve drafts and evidence; they do not promote experiments into the stable library or assign their implementation. See `provenance/sources.json` for exact refs.

## Layout changes

The 28 Agent Harness runtime folders moved to `skills/engineering`. Its project instructions and human guides remain in `examples/agent-harness`; the example uses the canonical library through discovery links. Upstream comparison moved to the library maintenance tools and a frozen baseline under provenance.

The four Agent Clarity folders moved to `skills/communication`; `explain` retains `metadata.internal: true`. Communication checker/build tests remain under `maintenance/communication`. Whole folders include examples, assets and native metadata.

The PR skill's legal reference is made self-contained. Style setup points at this repository. Other procedure semantics are preserved; project policy remains at the target project.

## Consumers and old links

Installed project copies remain usable at their selected versions. Exact copies can be adopted under a manifest; intentional adaptations remain project-owned. A source relocation does not authorize replacing local policy or editing installed provider packages.

On 2026-11-13, Agent Kit was published publicly and its bootstrap CI passed. Both original repositories were then archived; their commits remain readable. Their local checkouts remain in place because existing application registrations still refer to those paths.

The open Agent Harness board-skill issue was transferred to [Agent Kit #1](https://github.com/KirillSachkov/agent-kit/issues/1) without changing its requirements. Consolidation itself does not start that work.

The private Home consumer switched to the reviewed source commit `b0570c6006289437cd587a362d26b4594c987e26`. Six project branches prepared adoption of 69 exact shared copies. Their independent reviews and project checks passed; integration follows each project's own merge rules. Eighty intentional project variants were left unchanged. Publication does not imply that every consumer branch has merged.

Checks cover structure, source identities, complete folders and installer behavior. They do not prove that every external user or unindexed third-party installation has switched sources.
