#!/usr/bin/env python3

import argparse
import math
import re
import statistics


TRACE_PATTERN = re.compile(r"\[TRACE\](.*?)\[#TRACE\]", re.DOTALL)
LABEL_PATTERN = re.compile(r"^\s*data_labels\s*=\s*(.*?)\s*$", re.MULTILINE)
TRACE_DATA_PATTERN = re.compile(r"\[TRACE_DATA\](.*?)\[#TRACE_DATA\]", re.DOTALL)
LOGIC_THRESHOLD = 0.5
CLOCK_LOW_TOLERANCE = 0.1
HOLD_SAMPLE_FRACTION = 0.8
SAMPLE_WINDOW_RADIUS = 1
OUTPUT_PREFIXES = ("z", "izhod")
INPUT_PREFIX_ORDER = {"a": 0, "i": 1, "vhod": 2}
CLOCKS_PER_CYCLE = 4


def _logic_value(value: float):
    if value >= LOGIC_THRESHOLD:
        return 1
    if value <= -LOGIC_THRESHOLD:
        return 0
    return None


def _sample_logic(trace, sample_index, start=0, end=None):
    if end is None:
        end = len(trace)
    window = trace[
        max(start, sample_index - SAMPLE_WINDOW_RADIUS) :
        min(end, sample_index + SAMPLE_WINDOW_RADIUS + 1)
    ]
    logic_values = [_logic_value(value) for value in window]
    if not logic_values or None in logic_values or len(set(logic_values)) != 1:
        return None
    return logic_values[0]


def _parse_traces(s: str):
    traces = {}

    for trace_number, block in enumerate(TRACE_PATTERN.findall(s), 1):
        label_match = LABEL_PATTERN.search(block)
        data_match = TRACE_DATA_PATTERN.search(block)
        if label_match is None or data_match is None:
            raise ValueError(f"Trace {trace_number} is missing its label or data")

        label = label_match.group(1).strip()
        if not label:
            raise ValueError(f"Trace {trace_number} has an empty label")
        if label in traces:
            raise ValueError(f"Duplicate trace label: {label}")

        tokens = data_match.group(1).split()
        if not tokens:
            raise ValueError(f"Trace {label!r} contains no samples")

        try:
            values = [float(token.replace(",", ".")) for token in tokens]
        except ValueError as error:
            raise ValueError(f"Trace {label!r} contains an invalid sample") from error
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Trace {label!r} contains a non-finite sample")
        traces[label] = values

    if not traces:
        raise ValueError("No traces found")

    sample_counts = {len(values) for values in traces.values()}
    if len(sample_counts) != 1:
        raise ValueError("Traces have different sample counts")

    declared_samples = re.search(
        r"^\s*number_samples\s*=\s*(\d+)\s*$", s, re.MULTILINE
    )
    if declared_samples and int(declared_samples.group(1)) != sample_counts.pop():
        raise ValueError("number_samples does not match the trace data")

    return traces


def _clock_low_runs(trace):
    low_level = min(trace)
    high_level = max(trace)
    if high_level <= low_level:
        raise ValueError("Hold clock trace has no HIGH/LOW range")

    low_limit = low_level + (high_level - low_level) * CLOCK_LOW_TOLERANCE
    runs = []
    run_start = None
    for sample_index, value in enumerate(trace + [high_level]):
        if value <= low_limit:
            if run_start is None:
                run_start = sample_index
        elif run_start is not None:
            runs.append((run_start, sample_index))
            run_start = None
    return runs


def _input_sort_key(label):
    upper_label = label.upper()
    match = re.fullmatch(r"(.*?)(\d+)?", upper_label)
    prefix = match.group(1)
    port_number = match.group(2)
    return (
        INPUT_PREFIX_ORDER.get(prefix.casefold(), len(INPUT_PREFIX_ORDER)),
        prefix.casefold(),
        0 if port_number else 1,
        -int(port_number) if port_number else 0,
        upper_label,
    )


def _is_output_label(label):
    normalized_label = label.casefold()
    return any(normalized_label.startswith(prefix) for prefix in OUTPUT_PREFIXES)


def _is_clock_label(label):
    return label.upper().startswith("CLOCK")


def parse_simulation_results_into_table(
    s: str, delay_zones: int = 3
) -> str:
    if not isinstance(delay_zones, int) or delay_zones < 1:
        raise ValueError("Delay must be a positive number of clock zones")

    traces = _parse_traces(s)
    input_labels = sorted(
        (
            label
            for label in traces
            if not _is_clock_label(label) and not _is_output_label(label)
        ),
        key=_input_sort_key,
    )
    if not input_labels:
        raise ValueError("No input traces found")

    output_labels = sorted(
        (label for label in traces if _is_output_label(label)),
        key=_input_sort_key,
    )
    if not output_labels:
        raise ValueError(
            "No output traces found (expected names starting with 'Z' or 'Izhod')"
        )

    hold_clock_index = (delay_zones - 1) % CLOCKS_PER_CYCLE
    hold_clock = f"CLOCK {hold_clock_index}"
    clock_label = next(
        (label for label in traces if label.casefold() == hold_clock.casefold()),
        None,
    )
    if clock_label is None:
        raise ValueError(f"Hold clock trace {hold_clock!r} was not found")

    hold_runs = _clock_low_runs(traces[clock_label])
    if len(hold_runs) < 2:
        raise ValueError(f"Not enough HOLD periods in {clock_label!r}")

    cycle_samples = statistics.mean(
        end_start[0] - start[0]
        for start, end_start in zip(hold_runs, hold_runs[1:])
    )

    truth_table = {}
    for hold_start, hold_end in hold_runs:
        output_sample = min(
            hold_end - 1,
            hold_start + round((hold_end - hold_start) * HOLD_SAMPLE_FRACTION),
        )
        input_sample = round(
            output_sample - (delay_zones / CLOCKS_PER_CYCLE) * cycle_samples
        )
        vector = tuple(
            _sample_logic(traces[label], input_sample)
            for label in input_labels
        )
        if None in vector:
            continue

        outputs = tuple(
            _sample_logic(traces[label], output_sample, hold_start, hold_end)
            for label in output_labels
        )
        if None in outputs:
            continue

        if vector in truth_table and truth_table[vector] != outputs:
            raise ValueError(
                f"Conflicting output values for input "
                f"{dict(zip(input_labels, vector))}"
            )
        truth_table[vector] = outputs

    expected_combinations = 1 << len(input_labels)
    if len(truth_table) != expected_combinations:
        raise ValueError(
            f"Only {len(truth_table)} of {expected_combinations} input "
            "combinations have stable output samples"
        )

    header = input_labels + output_labels
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for vector in sorted(truth_table):
        values = [str(value) for value in vector]
        values.extend(str(value) for value in truth_table[vector])
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prebere rezultate simulacije in ustvari resničnostno tabelo"
    )
    parser.add_argument("input", help="Pot do simulacijskih rezultatov")
    parser.add_argument(
        "-o",
        "--output",
        help="Pot do izhodne resničnostne tabele v md (privzeto: <vhodna>.md)",
    )
    parser.add_argument(
        "--delay-zones",
        type=int,
        default=3,
        help="Delay from inputs to output, in clock zones (default: 3)",
    )
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or f"{input_path}.md"

    with open(input_path, "r", encoding="utf-8") as f:
        simulation_results = f.read()

    try:
        table = parse_simulation_results_into_table(
            simulation_results, args.delay_zones
        )
    except ValueError as error:
        parser.error(str(error))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(table)
