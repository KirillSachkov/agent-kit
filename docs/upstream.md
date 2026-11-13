# Engineering upstream

The engineering library derives from the Agent Harness public revision recorded in `provenance/sources.json`. Its 27 borrowed skills retain Matt Pocock's source revision `a496f5513d4a4cf889bc48e189e579f4b0bdf6aa`. `ship` is locally authored. The rename map retains `ask-matt` → `ask`.

Use the maintained tool to compare the current adaptation with the frozen source:

```bash
python3 tools/upstream.py --help
python3 tools/upstream.py diff
```

Pristine upstream is preserved losslessly under `provenance/upstream/mattpocock`; it is comparison input, not a second installable skill library. Keep its source digest, archive identity and complete notices. Review a three-way upstream update; a newer source date does not choose project policy.

Canonical skills are under `skills/engineering`. The example under `examples/agent-harness` retains the original project's policy. Its original [upstream guide](../examples/agent-harness/docs/upstream.en.md) records the adaptation history and maintenance reasoning.

Retain [Matt's MIT notice](../provenance/engineering/LICENSE.mattpocock), [HumanLayer's MIT notice](../provenance/engineering/LICENSE.humanlayer), [PR credits](../skills/engineering/pr/CREDITS.md), the root MIT license and NOTICE. A standalone PR skill includes its directly referenced HumanLayer license.
