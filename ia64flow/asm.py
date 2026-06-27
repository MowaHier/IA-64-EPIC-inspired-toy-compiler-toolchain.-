import re

from .model import Insn, Program


def clean(line: str) -> str:
    line = line.split("//", 1)[0]
    line = line.split("#", 1)[0]
    return line.strip()


def parse_pred(line: str) -> tuple[int, str]:
    m = re.match(r"^\(p(\d+)\)\s*(.*)$", line)
    if not m:
        return 0, line

    return int(m.group(1)), m.group(2).strip()


def parse_insn(line_no: int, line: str) -> Insn:
    pred, line = parse_pred(line)

    parts = line.split(None, 1)
    if not parts:
        raise RuntimeError(f"line {line_no}: empty instruction")

    op = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    rest = rest.replace("=", " = ")
    args = [x.strip() for x in re.split(r"[,\s]+", rest) if x.strip()]

    return Insn(
        line_no=line_no,
        text=line,
        pred=pred,
        op=op,
        args=args,
    )


def parse_program(src: str) -> Program:
    groups: list[list[Insn]] = []
    labels: dict[str, int] = {}
    cur: list[Insn] = []

    for line_no, raw in enumerate(src.splitlines(), start=1):
        line = clean(raw)

        if not line:
            continue

        if line.endswith(":"):
            if cur:
                groups.append(cur)
                cur = []

            label = line[:-1].strip()

            if label in labels:
                raise RuntimeError(f"line {line_no}: duplicate label: {label}")

            labels[label] = len(groups)
            continue

        stop = False

        if line.endswith(";;"):
            stop = True
            line = line[:-2].strip()

        if line:
            cur.append(parse_insn(line_no, line))

        if stop and cur:
            groups.append(cur)
            cur = []

    if cur:
        groups.append(cur)

    return Program(groups=groups, labels=labels)