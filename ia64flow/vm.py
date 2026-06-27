import re

from .asm import parse_program
from .model import Insn, Program


MASK64 = (1 << 64) - 1


class VM:
    def __init__(self, src: str | Program):
        if isinstance(src, Program):
            self.program = src
        else:
            self.program = parse_program(src)

        self.groups = self.program.groups
        self.labels = self.program.labels

        self.r = [0] * 128
        self.p = [False] * 64

        self.r[0] = 0
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
        if ins.op in ("mov", "add", "sub", "mul", "div"):
            return [ins.args[0]]

        if ins.op == "cmp.eq":
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
                        f"line {ins.line_no}: write conflict in same instruction group: {target}"
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
                self.set_r(new_r, dst, self.val(src, old_r))

            elif op == "add":
                dst, eq, x, y = a
                self.set_r(new_r, dst, self.val(x, old_r) + self.val(y, old_r))

            elif op == "sub":
                dst, eq, x, y = a
                self.set_r(new_r, dst, self.val(x, old_r) - self.val(y, old_r))

            elif op == "mul":
                dst, eq, x, y = a
                self.set_r(new_r, dst, self.val(x, old_r) * self.val(y, old_r))

            elif op == "div":
                dst, eq, x, y = a
                divisor = self.val(y, old_r)

                if divisor == 0:
                    raise RuntimeError(f"line {ins.line_no}: division by zero")

                self.set_r(new_r, dst, self.val(x, old_r) // divisor)

            elif op == "cmp.eq":
                pt, pf, eq, x, y = a
                result = self.val(x, old_r) == self.val(y, old_r)

                self.set_p(new_p, pt, result)
                self.set_p(new_p, pf, not result)

            elif op == "br.cond":
                if branch_target is None:
                    branch_target = a[0]

            else:
                raise RuntimeError(f"line {ins.line_no}: unknown op: {op}")

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
                return self

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


def run_asm(src: str, *, trace=False, max_steps=1000) -> VM:
    vm = VM(src)
    vm.run(max_steps=max_steps, trace=trace)
    return vm