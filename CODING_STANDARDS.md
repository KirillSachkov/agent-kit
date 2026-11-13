# Coding standards

- Python tooling uses the standard library and explicit argv lists for subprocesses. Run on Python 3.11 or later.
- Filesystem changes preflight the complete selected batch. Preserve unmanaged files, local modifications, unrelated settings and installed skills. Resolve a conflict rather than providing an overwrite switch.
- Selection uses immutable full commit SHAs. Preview is read-only. Installation retains complete skill folders and applicable license notices.
- Catalog entries identify canonical folders; supporting examples and frozen upstream baselines are not additional installable skills.
- Keep generic procedures separate from the target project's permissions, acceptance, testing and delivery rules.
- Test observable behavior through public command or module interfaces. Use synthetic repositories and directories; tests must not change real client configuration, authenticate accounts or publish anything.
- Source histories and provenance are evidence. Preserve old Git object IDs and record deliberate path, status or content changes.
