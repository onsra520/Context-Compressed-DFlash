from __future__ import annotations

# STATUS: skeleton-only entrypoint. Real benchmark/runtime wiring is intentionally deferred.

import argparse

from ccdf.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CCDF MVP entrypoint")
    parser.add_argument("--config", default="config.yml")
    args = parser.parse_args()

    config = load_config(args.config)
    print("Loaded config keys:", ", ".join(sorted(config)))
    raise NotImplementedError("MVP runtime wiring is intentionally left for the upstream code split.")


if __name__ == "__main__":
    main()