#!/usr/bin/env python3


def count_cells(file) -> int:
    with open(file, "r") as f:
        content = f.read()
        # we simply count number of QCAD_CELL_MODE_NORMAL
        return content.count("QCAD_CELL_MODE_NORMAL")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Count number of cells in a QCA file.")
    parser.add_argument("file", help="Input file path")
    args = parser.parse_args()

    num_cells = count_cells(args.file)
    print(f"Number of cells: {num_cells}")
