def empty_board(width: int, height: int) -> list[list[int]]:
    return [[0] * width for _ in range(height)]


def set_cell(board: list[list[int]], p: int, x: int, y: int, cell: list[int]) -> None:
    cx, cy = cell
    board[y + cy][x + cx] = p


def set_piece(
    board: list[list[int]], p: int, x: int, y: int, piece: list[list[int]]
) -> list[list[int]]:
    for cell in piece:
        set_cell(board, p, x, y, cell)
    return board
