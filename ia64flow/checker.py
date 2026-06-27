from dataclasses import dataclass
from pathlib import Path
import re


VALID_OPS = {
    "mov",
    "add",
    "sub",
    "mul",
    "div",
    "cmp.eq",
    "br.cond",
    "halt",
}


@dataclass
class CheckInsn:
    line_no: int
    text: str
    pred: int
    op: str
    args: list[str]


@dataclass
class CheckMessage:
    filename: str
    line_no: int
    level: str   # "error" or "warning"
    text: str

    def __str__(self) -> str:
        return f"{self.filename}:{self.line_no}: {self.level}: {self.text}"


def strip_comment(line: str) -> str:
    line = line.split("//", 1)[0]
    line = line.split("#", 1)[0]
    return line.strip()


def is_reg(token: str) -> bool:
    return re.fullmatch(r"r\d+", token) is not None


def is_pred(token: str) -> bool:
    return re.fullmatch(r"p\d+", token) is not None


def reg_num(token: str) -> int:
    return int(token[1:])


def pred_num(token: str) -> int:
    return int(token[1:])


def parse_predicate(line: str) -> tuple[int, str]:
    m = re.match(r"^\(p(\d+)\)\s*(.*)$", line)
    if not m:
        return 0, line

    return int(m.group(1)), m.group(2).strip()


def parse_insn(line_no: int, line: str) -> CheckInsn:
    pred, rest = parse_predicate(line)

    parts = rest.split(None, 1)

    if not parts:
        raise RuntimeError("empty instruction")

    op = parts[0]
    arg_text = parts[1] if len(parts) > 1 else ""

    arg_text = arg_text.replace("=", " = ")
    args = [x.strip() for x in re.split(r"[,\s]+", arg_text) if x.strip()]

    return CheckInsn(
        line_no=line_no,
        text=line,
        pred=pred,
        op=op,
        args=args,
    )


def reads_writes(ins: CheckInsn) -> tuple[set[str], set[str], set[str], set[str]]:
    reg_reads: set[str] = set()
    reg_writes: set[str] = set()
    pred_reads: set[str] = set()
    pred_writes: set[str] = set()

    if ins.pred != 0:
        pred_reads.add(f"p{ins.pred}")

    op = ins.op
    a = ins.args

    if op == "mov":
        dst, eq, src = a
        reg_writes.add(dst)

        if is_reg(src):
            reg_reads.add(src)

    elif op in ("add", "sub", "mul", "div"):
        dst, eq, x, y = a
        reg_writes.add(dst)

        if is_reg(x):
            reg_reads.add(x)

        if is_reg(y):
            reg_reads.add(y)

    elif op == "cmp.eq":
        pt, pf, eq, x, y = a
        pred_writes.add(pt)
        pred_writes.add(pf)

        if is_reg(x):
            reg_reads.add(x)

        if is_reg(y):
            reg_reads.add(y)

    elif op == "br.cond":
        pass

    elif op == "halt":
        pass

    return reg_reads, reg_writes, pred_reads, pred_writes


class Checker:
    def __init__(self, src: str, filename: str = "<memory>"):
        self.src = src
        self.filename = filename

        self.messages: list[CheckMessage] = []

        self.labels: dict[str, int] = {}
        self.branches: list[tuple[int, str]] = []
        self.groups: list[list[CheckInsn]] = []

    def error(self, line_no: int, text: str):
        self.messages.append(CheckMessage(self.filename, line_no, "error", text))

    def warning(self, line_no: int, text: str):
        self.messages.append(CheckMessage(self.filename, line_no, "warning", text))

    def parse(self):
        cur: list[CheckInsn] = []

        for idx, raw in enumerate(self.src.splitlines(), start=1):
            line = strip_comment(raw)

            if not line:
                continue

            stop = False

            if line.endswith(";;"):
                stop = True
                line = line[:-2].strip()

            if line == "":
                if stop and cur:
                    self.groups.append(cur)
                    cur = []
                continue

            if line.endswith(":"):
                label = line[:-1].strip()

                if not re.fullmatch(r"[A-Za-z_]\w*", label):
                    self.error(idx, f"bad label name: {label}")

                if label in self.labels:
                    self.error(idx, f"duplicate label: {label}")
                else:
                    self.labels[label] = idx

                if cur:
                    self.groups.append(cur)
                    cur = []

                continue

            try:
                ins = parse_insn(idx, line)
            except RuntimeError as e:
                self.error(idx, str(e))
                continue

            cur.append(ins)

            if stop and cur:
                self.groups.append(cur)
                cur = []

        if cur:
            self.groups.append(cur)

    def check_reg_token(self, line_no: int, token: str, *, write: bool):
        if not is_reg(token):
            self.error(line_no, f"expected register, got: {token}")
            return

        n = reg_num(token)

        if not (0 <= n < 128):
            self.error(line_no, f"register out of range: {token}")

        if write and n == 0:
            self.error(line_no, "r0 is read-only")

    def check_pred_token(self, line_no: int, token: str, *, write: bool):
        if not is_pred(token):
            self.error(line_no, f"expected predicate register, got: {token}")
            return

        n = pred_num(token)

        if not (0 <= n < 64):
            self.error(line_no, f"predicate out of range: {token}")

        if write and n == 0:
            self.error(line_no, "p0 is read-only")

    def check_value_token(self, line_no: int, token: str):
        if is_reg(token):
            self.check_reg_token(line_no, token, write=False)
            return

        if re.fullmatch(r"-?\d+", token):
            return

        self.error(line_no, f"expected register or integer, got: {token}")

    def check_insn_shape(self, ins: CheckInsn):
        if not (0 <= ins.pred < 64):
            self.error(ins.line_no, f"predicate out of range: p{ins.pred}")

        if ins.op not in VALID_OPS:
            self.error(ins.line_no, f"unknown instruction: {ins.op}")
            return

        a = ins.args

        if ins.op == "halt":
            if len(a) != 0:
                self.error(ins.line_no, "halt takes no arguments")
            return

        if ins.op == "br.cond":
            if len(a) != 1:
                self.error(ins.line_no, "br.cond expects: br.cond label")
            else:
                self.branches.append((ins.line_no, a[0]))
            return

        if ins.op == "mov":
            if len(a) != 3 or a[1] != "=":
                self.error(ins.line_no, "mov expects: mov rD = value")
                return

            self.check_reg_token(ins.line_no, a[0], write=True)
            self.check_value_token(ins.line_no, a[2])
            return

        if ins.op in ("add", "sub", "mul", "div"):
            if len(a) != 4 or a[1] != "=":
                self.error(ins.line_no, f"{ins.op} expects: {ins.op} rD = value,value")
                return

            self.check_reg_token(ins.line_no, a[0], write=True)
            self.check_value_token(ins.line_no, a[2])
            self.check_value_token(ins.line_no, a[3])
            return

        if ins.op == "cmp.eq":
            if len(a) != 5 or a[2] != "=":
                self.error(ins.line_no, "cmp.eq expects: cmp.eq pT,pF = value,value")
                return

            self.check_pred_token(ins.line_no, a[0], write=True)
            self.check_pred_token(ins.line_no, a[1], write=True)
            self.check_value_token(ins.line_no, a[3])
            self.check_value_token(ins.line_no, a[4])
            return

    def check_group(self, group: list[CheckInsn]):
        if len(group) > 3:
            self.error(
                group[3].line_no,
                f"instruction group has {len(group)} instructions; IA64Flow limit is 3"
            )

        reg_writers: dict[str, CheckInsn] = {}
        pred_writers: dict[str, CheckInsn] = {}

        previous_reg_writes: set[str] = set()
        previous_pred_writes: set[str] = set()

        for ins in group:
            reg_reads, reg_writes, pred_reads, pred_writes = reads_writes(ins)

            # RAW hazard:
            # A later instruction reads a value written earlier in the same group.
            # If it also writes that same register, let WAW report the clearer issue.
            effective_reg_reads = reg_reads - reg_writes

            for r in sorted(effective_reg_reads & previous_reg_writes):
                self.error(
                    ins.line_no,
                    f"RAW hazard in same group: {r} is read after being written earlier"
                )

            for p in sorted(pred_reads & previous_pred_writes):
                self.error(
                    ins.line_no,
                    f"predicate RAW hazard in same group: {p} is read after being written earlier"
                )

            # WAW conflict:
            # Two instructions write the same target in one group.
            for r in sorted(reg_writes):
                if r in reg_writers:
                    prev = reg_writers[r]

                    if ins.pred != 0 and prev.pred != 0 and ins.pred != prev.pred:
                        self.warning(
                            ins.line_no,
                            f"possible predicated WAW conflict: {r} also written at line {prev.line_no}"
                        )
                    else:
                        self.error(
                            ins.line_no,
                            f"WAW conflict in same group: {r} also written at line {prev.line_no}"
                        )

                reg_writers[r] = ins

            for p in sorted(pred_writes):
                if p in pred_writers:
                    prev = pred_writers[p]
                    self.error(
                        ins.line_no,
                        f"predicate WAW conflict in same group: {p} also written at line {prev.line_no}"
                    )

                pred_writers[p] = ins

            previous_reg_writes |= reg_writes
            previous_pred_writes |= pred_writes

    def check_branches(self):
        for line_no, label in self.branches:
            if label not in self.labels:
                self.error(line_no, f"unknown branch label: {label}")

    def check(self) -> list[CheckMessage]:
        self.parse()

        for group in self.groups:
            for ins in group:
                self.check_insn_shape(ins)

        # Shape errors may make reads_writes() unsafe.
        # Branch checks are still safe.
        if self.has_errors():
            self.check_branches()
            return self.messages

        for group in self.groups:
            self.check_group(group)

        self.check_branches()
        return self.messages

    def has_errors(self) -> bool:
        return any(m.level == "error" for m in self.messages)


def check_asm(src: str, filename: str = "<memory>") -> list[CheckMessage]:
    checker = Checker(src, filename=filename)
    return checker.check()


def check_file(path: str | Path) -> list[CheckMessage]:
    path = Path(path)
    src = path.read_text(encoding="utf-8")
    return check_asm(src, filename=str(path))