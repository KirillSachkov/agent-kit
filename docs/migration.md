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

Old repositories are archived after verified publication and controlled consumer switching. Archived commits and issue redirects retain the historical links used by existing installations. The open Agent Harness board-skill issue is transferred without changing its requirements; consolidation itself does not start that work.

Checks cover structure, source identities, complete folders and installer behavior. They do not prove that every external user or unindexed third-party installation has switched sources.
