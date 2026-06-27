from dataclasses import dataclass


@dataclass
class Insn:
    line_no: int
    text: str
    pred: int
    op: str
    args: list[str]


@dataclass
class Program:
    groups: list[list[Insn]]
    labels: dict[str, int]