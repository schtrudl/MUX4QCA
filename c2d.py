#!/usr/bin/env python3
import argparse
import sys

parser = argparse.ArgumentParser(description="Replace commas with dots in input text.")
parser.add_argument("file", help="Input file path or '-' for stdin")
args = parser.parse_args()

if args.file == "-":
    print(sys.stdin.read().replace(",", "."), end="")
else:
    with open(args.file, "r+") as f:
        content = f.read().replace(",", ".")
        f.seek(0)
        f.write(content)
        f.truncate()
