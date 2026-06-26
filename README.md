IA64Flow

IA64Flow is a small IA-64 / EPIC-inspired toy compiler toolchain written in Python.

It is not an Itanium emulator, not x86-64, and not Intel 64.
The goal is to experiment with IA-64-style ideas such as explicit instruction groups, stop markers, predicated execution, dependency checking, and compiler-driven scheduling.

What is included

IA64Flow currently contains:

ia64_vm.py — a small VM for running IA64Flow assembly
ia64flowc.py — a tiny .flow to .ia64 compiler
ia64opt.py — a simple instruction scheduler / optimizer
ia64check.py — a linter for dependency and scheduling errors
.vscode/tasks.json — VS Code task integration for checking .ia64 files
Concepts

IA64Flow uses a simplified IA-64-like execution model:

128 general registers: r0 to r127
64 predicate registers: p0 to p63
r0 is read-only zero
p0 is always true
;; marks the end of an instruction group
instructions in the same group read old state and commit together
the checker detects hazards such as WAW and RAW conflicts

Example:

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
Example workflow

Compile a .flow program:

python ia64flowc.py examples\while_sum.flow

Optimize the generated assembly:

python ia64opt.py examples\while_sum.ia64

Check the optimized assembly:

python ia64check.py examples\while_sum.opt.ia64

Run it on the VM:

python ia64_vm.py examples\while_sum.opt.ia64 --trace

Expected output:

r8 = 15
Example .flow program
let n = 5
let sum = 0

while n != 0:
    sum = sum + n
    n = n - 1

return sum
VS Code integration

The .vscode/tasks.json file provides a task for checking the current .ia64 file.

Run it with:

Ctrl + Shift + B

Errors and warnings from ia64check.py can appear in the VS Code Problems panel through a problem matcher.

Project status

This is an experimental educational project.

The purpose is to explore old EPIC / IA-64-style compiler ideas in a modern, lightweight Python toolchain:

.flow source
  -> compiler
  -> .ia64 assembly
  -> optimizer
  -> checker
  -> VM
Non-goals

IA64Flow is not intended to be:

a real Itanium emulator
a production compiler
an x86-64 assembler
a complete IA-64 implementation

It is a small playground for explicit scheduling, predication, dependency analysis, and compiler-toolchain experiments.
