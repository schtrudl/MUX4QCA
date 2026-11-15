gs := if os() == "windows" {
    'C:/Program Files/gs/gs10.08.0/bin/gswin64c.exe'
} else {
    'gs'
}

qcadesigner := if os() == "windows" {
    '"C:/Program Files (x86)/QCADesignerE/bin/QCADesignerE.exe"'
} else {
    '/home/samo/QCAD/bin/QCADesigner'
}

help:
    @just --list

c2d file:
    python c2d.py {{file}}

qca file:
    {{qcadesigner}} {{file}}
    python c2d.py {{file}}

render file:
    python eps2pdf.py "{{file}}" --gs "{{gs}}"