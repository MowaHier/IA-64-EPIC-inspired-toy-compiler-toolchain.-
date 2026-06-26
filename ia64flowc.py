from pathlib import Path
import sys
import re


def remove_comment(line: str) -> str:
    line = line.split("//", 1)[0]
    line = line.split("#", 1)[0]
    return line.rstrip()


def count_indent(line: str) -> int:
    if "\t" in line:
        raise RuntimeError("tabs are not allowed; use 4 spaces")

    return len(line) - len(line.lstrip(" "))


class Compiler:
    def __init__(self):
        self.vars: dict[str, str] = {}
        self.next_reg = 1
        self.next_label = 0
        self.out: list[str] = []

    def alloc(self, name: str) -> str:
        if name in self.vars:
            raise RuntimeError(f"variable already exists: {name}")

        if self.next_reg >= 128:
            raise RuntimeError("out of registers")

        reg = f"r{self.next_reg}"
        self.next_reg += 1
        self.vars[name] = reg
        return reg

    def get_var(self, name: str) -> str:
        if name not in self.vars:
            raise RuntimeError(f"unknown variable: {name}")
        return self.vars[name]

    def value(self, token: str) -> str:
        token = token.strip()

        if re.fullmatch(r"-?\d+", token):
            return token

        return self.get_var(token)

    def new_label(self, prefix: str) -> str:
        name = f"{prefix}_{self.next_label}"
        self.next_label += 1
        return name

    def emit(self, line: str):
        self.out.append(line)

    def stop(self):
        self.out.append(";;")

    def compile_expr_to(self, dst: str, expr: str):
        expr = expr.strip()

        m = re.fullmatch(r"(.+?)\s*([+\-])\s*(.+)", expr)
        if m:
            left = m.group(1).strip()
            op = m.group(2)
            right = m.group(3).strip()

            if op == "+":
                self.emit(f"add {dst} = {self.value(left)},{self.value(right)}")
            else:
                self.emit(f"sub {dst} = {self.value(left)},{self.value(right)}")

            self.stop()
            return

        self.emit(f"mov {dst} = {self.value(expr)}")
        self.stop()

    def compile_let(self, line: str):
        m = re.fullmatch(r"let\s+([A-Za-z_]\w*)\s*=\s*(.+)", line)
        if not m:
            raise RuntimeError(f"bad let syntax: {line}")

        name = m.group(1)
        expr = m.group(2)

        dst = self.alloc(name)
        self.compile_expr_to(dst, expr)

    def compile_assign(self, line: str):
        m = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*(.+)", line)
        if not m:
            raise RuntimeError(f"bad assignment syntax: {line}")

        name = m.group(1)
        expr = m.group(2)

        dst = self.get_var(name)
        self.compile_expr_to(dst, expr)

    def compile_return(self, line: str):
        expr = line[len("return "):].strip()
        self.compile_expr_to("r8", expr)
        self.emit("halt")

    def compile_simple_line(self, line: str):
        if line.startswith("let "):
            self.compile_let(line)
            return

        if line.startswith("return "):
            self.compile_return(line)
            return

        if "=" in line:
            self.compile_assign(line)
            return

        raise RuntimeError(f"unknown statement: {line}")

    def compile_while(self, lines: list[str], i: int, indent: int, stmt: str) -> int:
        m = re.fullmatch(r"while\s+(.+?)\s*(==|!=)\s*(.+):", stmt)
        if not m:
            raise RuntimeError(f"bad while syntax: {stmt}")

        left = m.group(1).strip()
        op = m.group(2)
        right = m.group(3).strip()

        loop_label = self.new_label("loop")
        end_label = self.new_label("end")

        self.emit(f"{loop_label}:")
        self.emit(f"cmp.eq p6,p7 = {self.value(left)},{self.value(right)}")
        self.stop()

        if op == "!=":
            # cmp.eq gives:
            # p6 = equal
            # p7 = not equal
            # while left != right should exit when p6 is true.
            self.emit(f"(p6) br.cond {end_label}")
        else:
            # while left == right should exit when p7 is true.
            self.emit(f"(p7) br.cond {end_label}")

        self.stop()

        body_start = i + 1
        if body_start >= len(lines):
            raise RuntimeError("while body is missing")

        next_i = self.compile_block(lines, body_start, indent + 4)

        if next_i == body_start:
            raise RuntimeError("while body is missing or not indented")

        self.emit(f"br.cond {loop_label}")
        self.stop()

        self.emit(f"{end_label}:")

        return next_i

    def compile_block(self, lines: list[str], i: int, indent: int) -> int:
        while i < len(lines):
            raw = remove_comment(lines[i])

            if not raw.strip():
                i += 1
                continue

            current_indent = count_indent(raw)

            if current_indent < indent:
                return i

            if current_indent > indent:
                raise RuntimeError(f"unexpected indentation: {raw}")

            stmt = raw[indent:].strip()

            if stmt.startswith("while "):
                i = self.compile_while(lines, i, indent, stmt)
                continue

            self.compile_simple_line(stmt)
            i += 1

        return i

    def compile(self, src: str) -> str:
        self.out.append("// generated by ia64flowc.py")
        self.out.append("")

        lines = src.splitlines()
        self.compile_block(lines, 0, 0)

        return "\n".join(self.out) + "\n"


def main():
    if len(sys.argv) < 2:
        print("usage: python ia64flowc.py input.flow [output.ia64]")
        sys.exit(1)

    in_path = Path(sys.argv[1])

    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
    else:
        out_path = in_path.with_suffix(".ia64")

    src = in_path.read_text(encoding="utf-8")

    compiler = Compiler()
    asm = compiler.compile(src)

    out_path.write_text(asm, encoding="utf-8")

    print(f"compiled: {in_path} -> {out_path}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("IA64Flow compiler error:", e)
        sys.exit(1)