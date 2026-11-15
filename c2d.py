#!/usr/bin/env python3
import argparse
import sys


def c2d(file):
    with open(file, "r+") as f:
        content = f.read().replace(",", ".")
        f.seek(0)
        f.write(content)
        f.truncate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Replace commas with dots in input text."
    )
    parser.add_argument("file", help="Input file path or '-' for stdin")
    args = parser.parse_args()

    if args.file == "-":
        print(sys.stdin.read().replace(",", "."), end="")
    else:
        c2d(args.file)
