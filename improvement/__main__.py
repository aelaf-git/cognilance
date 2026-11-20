"""Print the offline improvement report as JSON."""

from __future__ import annotations

import json

from improvement.propose import propose


def main() -> None:
    print(json.dumps(propose(), indent=2))


if __name__ == "__main__":
    main()
