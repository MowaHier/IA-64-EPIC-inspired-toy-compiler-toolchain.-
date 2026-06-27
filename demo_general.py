from ia64flow import compile_flow, optimize_asm, check_asm, run_asm


SOURCE = """
let jobs = 8
let completed = 0
let total_cost = 0
let cost = 3

while jobs != 0:
    completed = completed + 1
    total_cost = total_cost + cost
    cost = cost + 2
    jobs = jobs - 1

return total_cost
"""


def count_stops(asm: str) -> int:
    return sum(1 for line in asm.splitlines() if line.strip() == ";;")


def print_section(title: str):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main():
    print_section("IA64Flow General Demo")

    print(
        "This demo runs a tiny job-processing loop.\n"
        "It is not a real Itanium emulator.\n"
        "It shows how IA64Flow compiles, schedules, checks, and runs code."
    )

    print_section("1. Source program (.flow)")
    print(SOURCE.strip())

    print_section("2. Compile .flow -> IA64Flow assembly")
    asm = compile_flow(SOURCE)
    print(asm)

    print("Original stop marker count:", count_stops(asm))

    print_section("3. Optimize / schedule instruction groups")
    opt = optimize_asm(asm)
    print(opt)

    print("Optimized stop marker count:", count_stops(opt))

    print_section("4. Check optimized assembly")
    messages = check_asm(opt, filename="demo_general.opt.ia64")

    if messages:
        for msg in messages:
            print(msg)

        if any(msg.level == "error" for msg in messages):
            raise RuntimeError("checker found errors")
    else:
        print("OK: no scheduling errors found")

    print_section("5. Run on IA64Flow VM")
    vm = run_asm(opt, trace=False)

    print("Result register r8 =", vm.r[8])
    print()
    print("Expected result:")
    print("3 + 5 + 7 + 9 + 11 + 13 + 15 + 17 = 80")

    if vm.r[8] == 80:
        print()
        print("DEMO PASSED")
    else:
        raise RuntimeError(f"expected r8 = 80, got {vm.r[8]}")


if __name__ == "__main__":
    main()