from pathlib import Path
import sys

from ia64flow.checker import check_file


def main():
    if len(sys.argv) < 2:
        print("usage: python ia64check.py input.ia64")
        sys.exit(1)

    path = Path(sys.argv[1])
    messages = check_file(path)

    if messages:
        for msg in messages:
            print(msg)
    else:
        print(f"{path}: OK")

    if any(msg.level == "error" for msg in messages):
        sys.exit(1)


if __name__ == "__main__":
    main()