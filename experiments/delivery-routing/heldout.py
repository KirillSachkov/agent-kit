"""Run the participant's CLI in a disposable, network-isolated OS sandbox."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def execute(script, stdin):
    if not script.is_file() or script.is_symlink():
        raise ValueError("Missing or invalid product script")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        (work / "export.py").write_bytes(script.read_bytes())
        if sys.platform == "darwin":
            # Only runtime files and this copy of export.py are readable.
            runtime = [work, Path("/usr"), Path("/System"), Path("/Library/Apple"),
                       Path("/private/var/db/timezone"), Path("/opt/homebrew"),
                       Path(sys.base_prefix).resolve(), Path(sys.executable).resolve().parent]
            readable = " ".join(f"(subpath {json.dumps(str(p))})" for p in runtime)
            profile = ('(version 1)(deny default)(import "system.sb")(allow process-exec sysctl-read file-read-metadata)'
                       f"(allow file-read* {readable} (literal \"/dev/urandom\"))")
            argv = ["/usr/bin/sandbox-exec", "-p", profile, str(Path(sys.executable).resolve()), "-IBS", str(work / "export.py")]
        elif sys.platform.startswith("linux") and shutil.which("bwrap"):
            argv = ["bwrap", "--unshare-all", "--die-with-parent", "--dev", "/dev", "--proc", "/proc"]
            for path in ("/usr", "/lib", "/lib64", "/bin"):
                if Path(path).exists():
                    argv += ["--ro-bind", path, path]
            argv += ["--ro-bind", str(work), "/work", "--chdir", "/work", sys.executable, "-IBS", "/work/export.py"]
        else:
            raise OSError("Held-out check requires macOS sandbox-exec or Linux bubblewrap")
        return subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=10,
                              cwd=work, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
