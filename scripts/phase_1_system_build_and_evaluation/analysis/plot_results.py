from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot CCDF benchmark results")
    parser.add_argument("--results-dir", default="results")
    parser.parse_args()
    raise NotImplementedError("Plot generation is not wired yet.")


if __name__ == "__main__":
    main()