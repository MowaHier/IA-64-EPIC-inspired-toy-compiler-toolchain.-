# IA64Flow

> An IA-64 / EPIC-inspired toy compiler toolchain written in Python.

IA64Flow is a small experimental project for exploring old IA-64 / EPIC-style compiler ideas in a modern, lightweight Python toolchain.

It is **not** an Itanium emulator, **not** x86-64, and **not** Intel 64.

The goal is to experiment with concepts such as:

* explicit instruction groups
* stop markers
* predicated execution
* dependency checking
* simple compiler-driven scheduling
* IA-64-like optimization flow

---

## Overview

IA64Flow implements a tiny toolchain:

```text
.flow source
  -> compiler
  -> .ia64 assembly
  -> optimizer / scheduler
  -> checker / linter
  -> VM execution
```

The project is intentionally small and educational.
It is not intended to be a complete IA-64 implementation.

---

## Project Layout

```text
IA64Flow/
  README.md
  LICENSE
  .gitignore

  ia64_vm.py        # IA64Flow VM
  ia64flowc.py      # .flow -> .ia64 compiler
  ia64opt.py        # simple optimizer / scheduler
  ia64check.py      # checker / linter

  examples/
    assign_test.flow
    assign_test.ia64
    while_sum.flow
    while_sum.ia64
    while_sum.opt.ia64
    sum.ia64
    parallel_test.ia64
    predicate_test.ia64
    conflict_test.ia64
    raw_test.ia64

  .vscode/
    tasks.json
    settings.json
```

---

## Components

### `ia64_vm.py`

A small VM that executes IA64Flow assembly.

It currently supports:

* 128 general registers: `r0` to `r127`
* 64 predicate registers: `p0` to `p63`
* `r0` as read-only zero
* `p0` as always true
* `;;` as an instruction group stop marker
* predicated execution
* group commit behavior
* trace output
* basic scheduling validation

---

### `ia64flowc.py`

A tiny compiler that converts `.flow` source files into `.ia64` assembly.

Example `.flow` program:

```text
let n = 5
let sum = 0

while n != 0:
    sum = sum + n
    n = n - 1

return sum
```

Generated IA64Flow assembly will use labels, predicates, branches, and instruction groups.

---

### `ia64opt.py`

A simple optimizer / scheduler.

It attempts to pack independent instructions into the same instruction group when safe.

Example:

```asm
add r2 = r2,r1
sub r1 = r1,1
;;
```

Both instructions can share one group because they read the old register state and commit together.

---

### `ia64check.py`

A checker / linter for `.ia64` files.

It can detect:

* unknown instructions
* invalid registers
* invalid predicates
* writes to `r0`
* writes to `p0`
* duplicate labels
* missing branch targets
* WAW conflicts in the same group
* RAW hazards in the same group
* instruction groups larger than 3 instructions

Example error:

```text
examples\conflict_test.ia64:8: error: WAW conflict in same group: r1 also written at line 7
```

---

## IA64Flow Assembly Model

IA64Flow uses a simplified IA-64-like execution model.

Example:

```asm
mov r1 = 5
mov r2 = 0
;;

loop_0:
cmp.eq p6,p7 = r1,0
;;

(p6) br.cond end_1
;;

add r2 = r2,r1
sub r1 = r1,1
;;

br.cond loop_0
;;

end_1:
mov r8 = r2
;;

halt
```

Important rules:

* `;;` ends an instruction group.
* Instructions in the same group read old state.
* Results commit together at the end of the group.
* Predicated instructions only execute when their predicate is true.
* `r8` is used as the return/result register in examples.

---

## Quick Start

### 1. Compile a `.flow` program

```powershell
python ia64flowc.py examples\while_sum.flow
```

This generates:

```text
examples\while_sum.ia64
```

---

### 2. Optimize the generated assembly

```powershell
python ia64opt.py examples\while_sum.ia64
```

This generates:

```text
examples\while_sum.opt.ia64
```

---

### 3. Check the optimized assembly

```powershell
python ia64check.py examples\while_sum.opt.ia64
```

Expected output:

```text
examples\while_sum.opt.ia64: OK
```

---

### 4. Run it on the VM

```powershell
python ia64_vm.py examples\while_sum.opt.ia64 --trace
```

Expected final result:

```text
r8 = 15
```

---

## VS Code Integration

The project includes a simple VS Code task integration.

With `.vscode/tasks.json`, the current `.ia64` file can be checked through:

```text
Ctrl + Shift + B
```

The checker output can appear in the VS Code Problems panel through a problem matcher.

This is not a full language server yet.
It is a lightweight task-based checker integration.

---

## Example: WAW Conflict

Invalid IA64Flow assembly:

```asm
mov r1 = 10
;;

add r1 = r1,1
sub r1 = r1,1
;;

halt
```

Check it:

```powershell
python ia64check.py examples\conflict_test.ia64
```

Expected diagnostic:

```text
error: WAW conflict in same group
```

Both instructions write to `r1` in the same instruction group.

---

## Example: RAW Hazard

Invalid IA64Flow assembly:

```asm
mov r1 = 10
;;

add r2 = r1,1
add r3 = r2,1
;;

halt
```

The second instruction reads `r2`, but `r2` is written earlier in the same group.

In IA64Flow, instructions in the same group read old state, so this is likely a scheduling error.

---

## Requirements

* Python 3.10 or newer recommended
* VS Code optional, but useful for task integration

No external Python packages are required.

---

## Non-goals

IA64Flow is not:

* a real Itanium emulator
* a complete IA-64 assembler
* an x86-64 assembler
* Intel 64
* a production compiler
* a performance-oriented runtime

It is a small educational playground for explicit scheduling, predication, dependency analysis, and compiler-toolchain experiments.

---

## Why?

IA-64 / Itanium is often remembered as a failed architecture, but some of its compiler ideas are still interesting.

IA64Flow tries to turn those ideas into a small, readable, hackable toy project:

```text
make dependencies visible
make scheduling explicit
make the checker complain early
make the optimizer show its work
```

---

## License

MIT License is recommended for this project.
