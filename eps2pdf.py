#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import tempfile


def parse_margin(margin_values):
    """Pretvori od 1 do 4 CSS-like vrednosti roba v PostScript točke (top, right, bottom, left)."""
    unit_to_pt = {
        "cm": 72.0 / 2.54,
        "mm": 72.0 / 25.4,
        "in": 72.0,
        "pt": 1.0,
        "px": 72.0 / 96.0,
        "": 72.0 / 2.54,  # Privzeta enota brez pripone je cm
    }

    pts = []
    for val in margin_values:
        match = re.fullmatch(r"([+-]?(?:\d+\.?\d*|\.\d+))([a-zA-Z]*)", str(val).strip())
        if not match:
            raise ValueError(f"Neveljavna vrednost roba: '{val}'")
        num, unit = float(match.group(1)), match.group(2).lower()
        if unit not in unit_to_pt:
            raise ValueError(
                f"Nepodprta enota '{unit}' v '{val}'. Uporabite cm, mm, in, pt ali px."
            )
        pts.append(num * unit_to_pt[unit])

    # CSS pravila za 1, 2, 3 ali 4 vrednosti: (top, right, bottom, left)
    if len(pts) == 1:
        return pts[0], pts[0], pts[0], pts[0]
    elif len(pts) == 2:
        return pts[0], pts[1], pts[0], pts[1]
    elif len(pts) == 3:
        return pts[0], pts[1], pts[2], pts[1]
    elif len(pts) == 4:
        return pts[0], pts[1], pts[2], pts[3]
    else:
        raise ValueError("Rob mora vsebovati od 1 do 4 vrednosti.")


def convert_eps_to_pdf(gs_cmd, input_eps, output_pdf, margins=("1cm",)):
    top_pt, right_pt, bottom_pt, left_pt = parse_margin(margins)

    # 1. Izmeri dejanske meje vidnih pikslov z napravo 'bbox'
    bbox_cmd = [gs_cmd, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=bbox", input_eps]
    res = subprocess.run(bbox_cmd, capture_output=True, text=True, check=True)
    output_log = res.stdout + "\n" + res.stderr

    match = re.search(
        r"%%HiResBoundingBox:\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
        output_log,
    )
    if not match:
        print(
            f"Opozorilo: Ni bilo mogoče najti BoundingBox za {input_eps}. Uporabljam privzetega.",
            file=sys.stderr,
        )
        bbox_header = ""
    else:
        llx, lly, urx, ury = map(float, match.groups())
        # PostScript izhodišče (0,0) je spodaj levo:
        # levo/spodaj odštejemo, desno/zgoraj prištejemo
        llx -= left_pt
        lly -= bottom_pt
        urx += right_pt
        ury += top_pt

        bbox_header = (
            f"%%HiResBoundingBox: {llx:.4f} {lly:.4f} {urx:.4f} {ury:.4f}\n"
            f"%%BoundingBox: {int(llx)} {int(lly)} {int(urx + 1)} {int(ury + 1)}\n"
        )

    # 2. Preberi izvirni EPS in odstrani stare BoundingBox oznake
    with open(input_eps, "rb") as f:
        content = f.read()

    content = re.sub(
        rb"^%%(HiRes)?BoundingBox:.*?\r?\n", b"", content, flags=re.MULTILINE
    )

    # 3. Ustvari začasni EPS z novim, natančnim BoundingBoxom na vrhu
    fd, temp_eps = tempfile.mkstemp(suffix=".eps")
    try:
        with os.fdopen(fd, "wb") as tmp:
            header = f"%!PS-Adobe-3.0 EPSF-3.0\n{bbox_header}".encode("ascii")
            tmp.write(header)
            tmp.write(content)

        # 4. Pretvori v obrezan in stisnjen PDF
        pdf_cmd = [
            gs_cmd,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=pdfwrite",
            "-dEPSCrop",
            f"-sOutputFile={output_pdf}",
            temp_eps,
        ]
        subprocess.run(pdf_cmd, check=True)
    finally:
        if os.path.exists(temp_eps):
            os.remove(temp_eps)


if __name__ == "__main__":
    from c2d import c2d

    parser = argparse.ArgumentParser(
        description="Pretvori EPS v obrezan in stisnjen PDF z izračunom pravega BoundingBoxa."
    )
    parser.add_argument("input", help="Pot do vhodne EPS datoteke")
    parser.add_argument(
        "-o", "--output", help="Pot do izhodne PDF datoteke (privzeto: <vhodna>.pdf)"
    )
    parser.add_argument(
        "--gs",
        default="gs",
        help="Pot do izvedljive datoteke Ghostscript (privzeto: gs)",
    )
    parser.add_argument(
        "-m",
        "--margin",
        nargs="+",
        default=["1cm"],
        help="Rob v CSS slogu: 1 do 4 vrednosti (top right bottom left), enote cm/mm/in/pt/px (privzeto: 1cm)",
    )

    args = parser.parse_args()
    output_pdf = args.output if args.output else f"{args.input}.pdf"

    c2d(args.input)

    convert_eps_to_pdf(args.gs, args.input, output_pdf)
