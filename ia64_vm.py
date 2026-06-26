from dataclasses import dataclass
from pathlib import Path
import sys
import re

MASK64 = (1 << 64) - 1


@dataclass
class Insn:
    pred: int
    op: str
    args: list[str]


def clean(line: str) -> str:
    line = line.split("//", 1)[0]
    line = line.split("#", 1)[0]
    return line.strip()


def parse_pred(line: str) -> tuple[int, str]:
    m = re.match(r"^\(p(\d+)\)\s*(.*)$", line)
    if not m:
        return 0, line
    return int(m.group(1)), m.group(2).strip()


def parse_insn(line: str) -> Insn:
    pred, line = parse_pred(line)
    parts = line.split(None, 1)
    if not parts:
        raise RuntimeError("empty instruction")

    op = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    rest = rest.replace("=", " = ")
    args = [x.strip() for x in re.split(r"[,\s]+", rest) if x.strip()]

    return Insn(pred, op, args)


def parse_program(src: str):
    groups: list[list[Insn]] = []
    labels: dict[str, int] = {}
    cur: list[Insn] = []

    for raw in src.splitlines():
        line = clean(raw)
        if not line:
            continue

        if line.endswith(":"):
            if cur:
                groups.append(cur)
                cur = []
            labels[line[:-1]] = len(groups)
            continue

        stop = False
        if line.endswith(";;"):
            stop = True
            line = line[:-2].strip()

        if line:
            cur.append(parse_insn(line))

        if stop and cur:
            groups.append(cur)
            cur = []

    if cur:
        groups.append(cur)

    return groups, labels


class VM:
    def __init__(self, src: str):
        self.groups, self.labels = parse_program(src)

        self.r = [0] * 128
        self.p = [False] * 64

        self.p[0] = True
        self.ip = 0
        self.halted = False

    def gr(self, name: str) -> int:
        if not re.fullmatch(r"r\d+", name):
            raise RuntimeError(f"bad register: {name}")

        n = int(name[1:])
        if not (0 <= n < 128):
            raise RuntimeError(f"register out of range: {name}")

        return n

    def pr(self, name: str) -> int:
        if not re.fullmatch(r"p\d+", name):
            raise RuntimeError(f"bad predicate register: {name}")

        n = int(name[1:])
        if not (0 <= n < 64):
            raise RuntimeError(f"predicate register out of range: {name}")

        return n

    def val(self, token: str, old_r: list[int]) -> int:
        if token.startswith("r"):
            return old_r[self.gr(token)]
        return int(token, 0)

    def set_r(self, new_r: list[int], dst: str, value: int):
        n = self.gr(dst)

        if n == 0:
            raise RuntimeError("r0 is read-only")

        new_r[n] = value & MASK64

    def set_p(self, new_p: list[bool], dst: str, value: bool):
        n = self.pr(dst)

        if n == 0:
            return

        new_p[n] = bool(value)

    def write_targets(self, ins: Insn) -> list[str]:
        if ins.op in ("mov", "add", "sub"):
            return [ins.args[0]]

        if ins.op in ("cmp.eq", "cmp.ne"):
            return [ins.args[0], ins.args[1]]

        return []

    def validate_group_writes(self, group: list[Insn], old_p: list[bool]):
        written: dict[str, Insn] = {}

        for ins in group:
            if not old_p[ins.pred]:
                continue

            for target in self.write_targets(ins):
                if target in written:
                    raise RuntimeError(
                        f"write conflict in same instruction group: {target}"
                    )

                written[target] = ins

    def step(self):
        if self.halted:
            return

        if self.ip >= len(self.groups):
            self.halted = True
            return

        group = self.groups[self.ip]

        old_r = self.r[:]
        old_p = self.p[:]

        self.validate_group_writes(group, old_p)

        new_r = old_r[:]
        new_p = old_p[:]

        branch_target = None

        for ins in group:
            if not old_p[ins.pred]:
                continue

            op = ins.op
            a = ins.args

            if op == "halt":
                self.halted = True

            elif op == "mov":
                dst, eq, src = a
                if eq != "=":
                    raise RuntimeError("expected '=' in mov")
                self.set_r(new_r, dst, self.val(src, old_r))

            elif op == "add":
                dst, eq, x, y = a
                if eq != "=":
                    raise RuntimeError("expected '=' in add")
                self.set_r(new_r, dst, self.val(x, old_r) + self.val(y, old_r))

            elif op == "sub":
                dst, eq, x, y = a
                if eq != "=":
                    raise RuntimeError("expected '=' in sub")
                self.set_r(new_r, dst, self.val(x, old_r) - self.val(y, old_r))

            elif op == "cmp.eq":
                pt, pf, eq, x, y = a
                if eq != "=":
                    raise RuntimeError("expected '=' in cmp.eq")
                result = self.val(x, old_r) == self.val(y, old_r)
                self.set_p(new_p, pt, result)
                self.set_p(new_p, pf, not result)

            elif op == "cmp.ne":
                pt, pf, eq, x, y = a
                if eq != "=":
                    raise RuntimeError("expected '=' in cmp.ne")
                result = self.val(x, old_r) != self.val(y, old_r)
                self.set_p(new_p, pt, result)
                self.set_p(new_p, pf, not result)

            elif op == "br.cond":
                if branch_target is None:
                    branch_target = a[0]

            else:
                raise RuntimeError(f"unknown op: {op}")

        new_r[0] = 0
        new_p[0] = True

        self.r = new_r
        self.p = new_p

        if branch_target is not None:
            if branch_target not in self.labels:
                raise RuntimeError(f"unknown label: {branch_target}")
            self.ip = self.labels[branch_target]
        else:
            self.ip += 1

    def dump_core(self) -> str:
        return (
            f"ip={self.ip} | "
            f"r1={self.r[1]} r2={self.r[2]} "
            f"r3={self.r[3]} r4={self.r[4]} r8={self.r[8]} | "
            f"p6={int(self.p[6])} p7={int(self.p[7])}"
        )

    def format_insn(self, ins: Insn) -> str:
        pred = "" if ins.pred == 0 else f"(p{ins.pred}) "
        return pred + ins.op + " " + ",".join(ins.args)

    def run(self, max_steps=1000, trace=False):
        for step_no in range(max_steps):
            if self.halted:
                return

            if trace:
                print()
                print(f"STEP {step_no}")
                print("BEFORE:", self.dump_core())

                if self.ip < len(self.groups):
                    print("GROUP:")
                    for ins in self.groups[self.ip]:
                        print("  ", self.format_insn(ins))

            self.step()

            if trace:
                print("AFTER: ", self.dump_core())

        raise RuntimeError("max steps exceeded")


def main():
    trace = "--trace" in sys.argv

    args = [arg for arg in sys.argv[1:] if arg != "--trace"]

    if len(args) >= 1:
        path = Path(args[0])
    else:
        path = Path("sum.ia64")

    src = path.read_text(encoding="utf-8")

    vm = VM(src)
    vm.run(trace=trace)

    print()
    print("r8 =", vm.r[8])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print()
        print("IA64Flow error:", e)
        sys.exit(1)
