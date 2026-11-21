#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


def _parse_table(text, output_column):
    rows = [
        [value.strip() for value in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.strip().startswith("|")
    ]
    if len(rows) < 3:
        raise ValueError("Expected a Markdown table with a header and data rows")

    headers = rows[0]
    if len(set(header.casefold() for header in headers)) != len(headers):
        raise ValueError("Table contains duplicate column names")
    if len(rows[1]) != len(headers) or not all(
        re.fullmatch(r":?-{3,}:?", value) for value in rows[1]
    ):
        raise ValueError("Table is missing its Markdown separator row")

    output_index = next(
        (
            index
            for index, header in enumerate(headers)
            if header.casefold() == output_column.casefold()
        ),
        None,
    )
    if output_index is None:
        raise ValueError(f"Output column {output_column!r} was not found")

    input_columns = [
        (index, header) for index, header in enumerate(headers) if index != output_index
    ]
    if not input_columns:
        raise ValueError("Table must contain at least one input column")

    table = {}
    for row_number, row in enumerate(rows[2:], 3):
        if len(row) != len(headers):
            raise ValueError(f"Row {row_number} has the wrong number of columns")
        if any(value not in {"0", "1"} for value in row):
            raise ValueError(f"Row {row_number} contains a non-binary value")

        vector = tuple(row[index] for index, _ in input_columns)
        if vector in table:
            raise ValueError(f"Duplicate input combination on row {row_number}")
        table[vector] = row[output_index]

    expected_rows = 1 << len(input_columns)
    if len(table) != expected_rows:
        raise ValueError(
            f"Table has {len(table)} input combinations; expected {expected_rows}"
        )

    return [header for _, header in input_columns], table, headers[output_index]


def _reduced_mux_table(variables, table, output_column):
    selectors = {}
    data_inputs = {}
    for variable in variables:
        selector_match = re.fullmatch(r"A(\d+)", variable, re.IGNORECASE)
        data_match = re.fullmatch(r"I(\d+)", variable, re.IGNORECASE)
        if selector_match:
            index = int(selector_match.group(1))
            if index in selectors:
                raise ValueError(f"Duplicate selector index A{index}")
            selectors[index] = variable
        elif data_match:
            index = int(data_match.group(1))
            if index in data_inputs:
                raise ValueError(f"Duplicate data input index I{index}")
            data_inputs[index] = variable
        else:
            raise ValueError(
                f"Input {variable!r} is not a selector (A<n>) or data input (I<n>)"
            )

    selector_count = len(selectors)
    if not selector_count or set(selectors) != set(range(selector_count)):
        raise ValueError("Selector columns must be numbered consecutively from A0")
    data_count = 1 << selector_count
    if set(data_inputs) != set(range(data_count)):
        raise ValueError(
            f"Expected data input columns I0 through I{data_count - 1}"
        )

    selector_columns = [
        selectors[index] for index in reversed(range(selector_count))
    ]
    variable_positions = {
        variable.casefold(): index for index, variable in enumerate(variables)
    }

    for vector, output in table.items():
        selected_index = sum(
            int(vector[variable_positions[selectors[index].casefold()]]) << index
            for index in range(selector_count)
        )
        selected_input = data_inputs[selected_index]
        expected = vector[variable_positions[selected_input.casefold()]]
        if output != expected:
            raise ValueError(
                f"Table is not a multiplexer: {output_column} differs from "
                f"{selected_input} for input {dict(zip(variables, vector))}"
            )

    lines = [
        "| " + " | ".join(selector_columns + [output_column]) + " |",
        "| " + " | ".join("---" for _ in selector_columns + [output_column]) + " |",
    ]
    for selected_index in range(data_count):
        selector_values = [
            str((selected_index >> index) & 1)
            for index in reversed(range(selector_count))
        ]
        lines.append(
            "| "
            + " | ".join(selector_values + [data_inputs[selected_index]])
            + " |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Reduce a multiplexer truth table to selector-to-input Markdown"
    )
    parser.add_argument("input", help="Path to a Markdown truth table")
    parser.add_argument(
        "--output-column",
        default="Z",
        help="Output column to simplify (default: Z)",
    )
    args = parser.parse_args()

    try:
        text = Path(args.input).read_text(encoding="utf-8")
        variables, table, output_column = _parse_table(text, args.output_column)
        markdown = _reduced_mux_table(variables, table, output_column)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(markdown)


if __name__ == "__main__":
    main()
