from ia64flow import compile_flow, optimize_asm, check_asm, run_asm


SOURCE = """
let n = 5
let sum = 0

while n != 0:
    sum = sum + n
    n = n - 1

return sum
"""


def main():
    print("=== compile ===")
    asm = compile_flow(SOURCE)
    print(asm)

    print("=== optimize ===")
    opt = optimize_asm(asm)
    print(opt)

    print("=== check ===")
    messages = check_asm(opt, filename="smoke_test.opt.ia64")

    if messages:
        for msg in messages:
            print(msg)

        if any(msg.level == "error" for msg in messages):
            raise RuntimeError("checker found errors")
    else:
        print("OK")

    print("=== run ===")
    vm = run_asm(opt, trace=False)

    print("r8 =", vm.r[8])

    if vm.r[8] != 15:
        raise RuntimeError(f"expected r8 = 15, got {vm.r[8]}")

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()