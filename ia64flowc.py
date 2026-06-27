from pathlib import Path
import sys

from ia64flow.compiler import compile_file


def main():
    if len(sys.argv) < 2:
        print("usage: python ia64flowc.py input.flow [output.ia64]")
        sys.exit(1)

    in_path = Path(sys.argv[1])

    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
    else:
        out_path = None

    result_path = compile_file(in_path, out_path)

    print(f"compiled: {in_path} -> {result_path}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("IA64Flow compiler error:", e)
        sys.exit(1)