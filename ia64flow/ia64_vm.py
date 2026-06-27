from pathlib import Path
import sys

from ia64flow import VM


def main():
    trace = "--trace" in sys.argv

    args = [arg for arg in sys.argv[1:] if arg != "--trace"]

    if len(args) >= 1:
        path = Path(args[0])
    else:
        path = Path("examples/sum.ia64")

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
        print("IA64Flow VM error:", e)
        sys.exit(1)