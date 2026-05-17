from xagent.piece import shape

I = 1
Z = 2
S = 3
J = 4
L = 5
T = 6
O = 7


def piece(p: int, rotation: int) -> list[list[int]]:
    return shape.pieces[p][rotation]  # type: ignore[index]
