#!/bin/sh
# The project's required CI check. The local CI double runs it on the pushed revision.
set -e
python3 -m unittest discover -s tests -q
grep -q 'python3 greet.py <name>' README.md || {
  echo "docs check failed: README.md must show the usage line: python3 greet.py <name>"
  exit 1
}
