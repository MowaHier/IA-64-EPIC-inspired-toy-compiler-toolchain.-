from pathlib import Path
import sys
import re


SIMPLE_OPS = {"mov", "add", "sub"}


def strip_comment(line: str) -> str:
    line = line.split("//", 1)[0]
    line = line.split("#", 1)[0]
    return line.strip()


def remove_predicate(line: str) -> str:
    m = re.match(r"^\(p\d+\)\s*(.*)$", line)
    if m:
        return m.group(1).strip()
    return line


def split_insn(line: str) -> tuple[str, list[str]]:
    line = remove_predicate(line)

    parts = line.split(None, 1)
    op = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    rest = rest.replace("=", " = ")
    args = [x.strip() for x in re.split(r"[,\s]+", rest) if x.strip()]

    return op, args


def is_reg(token: str) -> bool:
    return re.fullmatch(r"r\d+", token) is not None


def reads_writes(line: str) -> tuple[set[str], set[str]]:
    op, args = split_insn(line)

    reads: set[str] = set()
    writes: set[str] = set()

    if op == "mov":
        dst, eq, src = args
        writes.add(dst)
        if is_reg(src):
            reads.add(src)

    elif op in ("add", "sub"):
        dst, eq, x, y = args
        writes.add(dst)
        if is_reg(x):
            reads.add(x)
        if is_reg(y):
            reads.add(y)

    return reads, writes


def is_simple(line: str) -> bool:
    op, args = split_insn(line)
    return op in SIMPLE_OPS


class Optimizer:
    def __init__(self):
        self.out: list[str] = []
        self.buf: list[str] = []

    def emit(self, line: str):
        self.out.append(line)

    def flush(self):
        if not self.buf:
            return

        for line in self.buf:
            self.emit(line)

        self.emit(";;")
        self.buf.clear()

    def can_pack(self, line: str) -> bool:
        if len(self.buf) >= 3:
            return False

        new_reads, new_writes = reads_writes(line)

        old_writes: set[str] = set()

        for old in self.buf:
            _, w = reads_writes(old)
            old_writes |= w

        # RAW hazard:
        # New instruction wants to read a value produced earlier in this group.
        # That cannot be packed, because group instructions read old state.
        if new_reads & old_writes:
            return False

        # WAW hazard:
        # Two instructions write the same register in one group.
        if new_writes & old_writes:
            return False

        return True

    def add_simple(self, line: str):
        if not self.can_pack(line):
            self.flush()

        self.buf.append(line)

    def add_barrier(self, line: str):
        self.flush()

        if line.endswith(":"):
            self.emit(line)
            return

        self.emit(line)

        if line != "halt":
            self.emit(";;")

    def optimize(self, src: str) -> str:
        self.emit("// optimized by ia64opt.py")
        self.emit("")

        for raw in src.splitlines():
            line = strip_comment(raw)

            if not line:
                continue

            if line == ";;":
                continue

            if line.endswith(":"):
                self.add_barrier(line)
                continue

            op, _ = split_insn(line)

            if op in SIMPLE_OPS:
                self.add_simple(line)
                continue

            # cmp, branch, halt, unknown/control-like ops are barriers.
            self.add_barrier(line)

        self.flush()

        return "\n".join(self.out) + "\n"


def main():
    if len(sys.argv) < 2:
        print("usage: python ia64opt.py input.ia64 [output.ia64]")
        sys.exit(1)

    in_path = Path(sys.argv[1])

    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
    else:
        out_path = in_path.with_name(in_path.stem + ".opt.ia64")

    src = in_path.read_text(encoding="utf-8")

    opt = Optimizer()
    asm = opt.optimize(src)

    out_path.write_text(asm, encoding="utf-8")

    print(f"optimized: {in_path} -> {out_path}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("IA64Flow optimizer error:", e)
        sys.exit(1)