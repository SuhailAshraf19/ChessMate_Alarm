"""
utils/chess_engine.py
Full chess logic: FEN parsing, complete legal move generation
(including check detection), and UCI move application.
No external dependencies.
"""

EMPTY = "."

PIECE_UNICODE = {
    "K": "♚", "Q": "♛", "R": "♜", "B": "♝", "N": "♞", "P": "♟",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
    ".": " ",
}


class Board:

    def __init__(self, fen: str):
        self.grid = [[EMPTY] * 8 for _ in range(8)]
        self.turn = "w"
        self.castling = "-"
        self.en_passant = "-"
        self.halfmove = 0
        self.fullmove = 1
        self._parse_fen(fen)

    def _parse_fen(self, fen: str):
        parts = fen.split()
        for r, row_str in enumerate(parts[0].split("/")):
            c = 0
            for ch in row_str:
                if ch.isdigit():
                    c += int(ch)
                else:
                    self.grid[r][c] = ch
                    c += 1
        self.turn       = parts[1] if len(parts) > 1 else "w"
        self.castling   = parts[2] if len(parts) > 2 else "-"
        self.en_passant = parts[3] if len(parts) > 3 else "-"
        self.halfmove   = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove   = int(parts[5]) if len(parts) > 5 else 1

    def piece_at(self, col: int, row: int) -> str:
        if 0 <= col <= 7 and 0 <= row <= 7:
            return self.grid[row][col]
        return EMPTY

    # ─────────────────────────────────────────────────────────────────────
    # Legal move generation
    # ─────────────────────────────────────────────────────────────────────

    def legal_moves_from(self, col: int, row: int) -> list:
        """
        Return list of (col, row) destination squares the piece on
        (col, row) can legally move to.
        """
        piece = self.piece_at(col, row)
        if piece == EMPTY:
            return []
        is_white = piece.isupper()
        # Pass True to _pseudo_moves to avoid recursion during check detection
        pseudo = self._pseudo_moves(piece.upper(), col, row, is_white, check_castling=True)
        legal = []
        for tc, tr in pseudo:
            b2 = self._apply_move_raw(col, row, tc, tr)
            if not b2._king_in_check(is_white):
                legal.append((tc, tr))
        return legal

    def _pseudo_moves(self, piece_type: str, col: int, row: int,
                      is_white: bool, check_castling: bool = False) -> list:
        moves = []

        def in_bounds(c, r):
            return 0 <= c <= 7 and 0 <= r <= 7

        def is_enemy(c, r):
            p = self.piece_at(c, r)
            return p != EMPTY and (p.isupper() != is_white)

        def is_empty(c, r):
            return self.piece_at(c, r) == EMPTY

        def is_friendly(c, r):
            p = self.piece_at(c, r)
            return p != EMPTY and (p.isupper() == is_white)

        def slide(directions):
            for dc, dr in directions:
                c, r = col + dc, row + dr
                while in_bounds(c, r):
                    if is_empty(c, r):
                        moves.append((c, r))
                    elif is_enemy(c, r):
                        moves.append((c, r))
                        break
                    else:
                        break
                    c += dc
                    r += dr

        def step(directions):
            for dc, dr in directions:
                c, r = col + dc, row + dr
                if in_bounds(c, r) and not is_friendly(c, r):
                    moves.append((c, r))

        if piece_type == "R":
            slide([(1,0),(-1,0),(0,1),(0,-1)])

        elif piece_type == "B":
            slide([(1,1),(1,-1),(-1,1),(-1,-1)])

        elif piece_type == "Q":
            slide([(1,0),(-1,0),(0,1),(0,-1),
                   (1,1),(1,-1),(-1,1),(-1,-1)])

        elif piece_type == "N":
            step([(2,1),(2,-1),(-2,1),(-2,-1),
                  (1,2),(1,-2),(-1,2),(-1,-2)])

        elif piece_type == "K":
            step([(1,0),(-1,0),(0,1),(0,-1),
                  (1,1),(1,-1),(-1,1),(-1,-1)])
            # Castling (only check if check_castling is True to avoid recursion)
            if check_castling and not self._king_in_check(is_white):
                if is_white and row == 7 and col == 4:
                    if "K" in self.castling and self.piece_at(5, 7) == EMPTY and self.piece_at(6, 7) == EMPTY:
                        moves.append((6, 7))
                    if "Q" in self.castling and self.piece_at(1, 7) == EMPTY and self.piece_at(2, 7) == EMPTY and self.piece_at(3, 7) == EMPTY:
                        moves.append((2, 7))
                elif not is_white and row == 0 and col == 4:
                    if "k" in self.castling and self.piece_at(5, 0) == EMPTY and self.piece_at(6, 0) == EMPTY:
                        moves.append((6, 0))
                    if "q" in self.castling and self.piece_at(1, 0) == EMPTY and self.piece_at(2, 0) == EMPTY and self.piece_at(3, 0) == EMPTY:
                        moves.append((2, 0))

        elif piece_type == "P":
            # White pawns move up (row decreases), black down (row increases)
            fwd = -1 if is_white else 1
            start_row = 6 if is_white else 1

            # One step forward
            r1 = row + fwd
            if in_bounds(col, r1) and is_empty(col, r1):
                moves.append((col, r1))
                # Two steps from starting row
                r2 = row + 2 * fwd
                if row == start_row and in_bounds(col, r2) and is_empty(col, r2):
                    moves.append((col, r2))

            # Diagonal captures
            for dc in [-1, 1]:
                c, r = col + dc, row + fwd
                if in_bounds(c, r) and is_enemy(c, r):
                    moves.append((c, r))
            
            # En passant
            if self.en_passant != "-":
                ep_col = ord(self.en_passant[0]) - ord("a")
                ep_row = 8 - int(self.en_passant[1])
                for dc in [-1, 1]:
                    c = col + dc
                    if c == ep_col and row + fwd == ep_row:
                        moves.append((c, ep_row))

        return moves

    def _apply_move_raw(self, fc: int, fr: int, tc: int, tr: int) -> "Board":
        """Apply move without legality checks — used for check detection."""
        new_grid = [row[:] for row in self.grid]
        piece = new_grid[fr][fc]
        new_grid[tr][tc] = piece
        new_grid[fr][fc] = EMPTY
        
        # Handle en passant capture
        if piece.upper() == "P" and self.en_passant != "-":
            ep_col = ord(self.en_passant[0]) - ord("a")
            ep_row = 8 - int(self.en_passant[1])
            if tc == ep_col and tr == ep_row:
                # Remove captured pawn
                capture_row = fr
                new_grid[capture_row][tc] = EMPTY
        
        b = Board.__new__(Board)
        b.grid = new_grid
        b.turn = "b" if self.turn == "w" else "w"
        b.castling = self.castling
        b.en_passant = "-"
        b.halfmove = self.halfmove
        b.fullmove = self.fullmove
        return b

    def _king_in_check(self, is_white: bool) -> bool:
        """Return True if the king of is_white is under attack."""
        king_char = "K" if is_white else "k"
        kc, kr = -1, -1
        for r in range(8):
            for c in range(8):
                if self.grid[r][c] == king_char:
                    kc, kr = c, r
                    break
            if kc != -1:
                break
        if kc == -1:
            return False   # no king found (shouldn't happen)

        # Check if any opponent piece attacks (kc, kr)
        opp_white = not is_white
        for r in range(8):
            for c in range(8):
                p = self.grid[r][c]
                if p == EMPTY:
                    continue
                if p.isupper() != opp_white:
                    continue
                # Use pseudo moves of opponent piece
                for tc, tr in self._pseudo_moves(p.upper(), c, r, opp_white):
                    if tc == kc and tr == kr:
                        return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Apply UCI move (returns new Board)
    # ─────────────────────────────────────────────────────────────────────

    def apply_uci(self, uci: str) -> "Board":
        fc, fr, tc, tr = _uci_to_coords(uci)
        new_grid = [row[:] for row in self.grid]
        piece = new_grid[fr][fc]
        new_grid[tr][tc] = piece
        new_grid[fr][fc] = EMPTY
        
        # Handle castling move (move the rook too)
        if piece.upper() == "K" and abs(fc - tc) == 2:
            rook_fr = fr
            if tc == 6:  # King side
                new_grid[rook_fr][5] = new_grid[rook_fr][7]
                new_grid[rook_fr][7] = EMPTY
            elif tc == 2:  # Queen side
                new_grid[rook_fr][3] = new_grid[rook_fr][0]
                new_grid[rook_fr][0] = EMPTY

        # Handle en passant capture
        if piece.upper() == "P" and self.en_passant != "-":
            ep_col = ord(self.en_passant[0]) - ord("a")
            ep_row = 8 - int(self.en_passant[1])
            if tc == ep_col and tr == ep_row:
                new_grid[fr][tc] = EMPTY

        # Promotion
        if len(uci) == 5:
            promo = uci[4].upper() if piece.isupper() else uci[4].lower()
            new_grid[tr][tc] = promo
        
        # Calculate new en passant
        new_en_passant = "-"
        if piece.upper() == "P" and abs(fr - tr) == 2:
            new_en_passant = chr(ord("a") + fc) + str(8 - (fr + tr) // 2)

        # Handle castling rights
        nc = self.castling
        if piece.upper() == "K":
            if self.turn == "w":
                nc = nc.replace("K", "").replace("Q", "")
            else:
                nc = nc.replace("k", "").replace("q", "")

        # Rook moves or is captured
        def _update_cr(c, r):
            nonlocal nc
            if r == 7 and c == 7: nc = nc.replace("K", "")
            if r == 7 and c == 0: nc = nc.replace("Q", "")
            if r == 0 and c == 7: nc = nc.replace("k", "")
            if r == 0 and c == 0: nc = nc.replace("q", "")

        _update_cr(fc, fr)
        _update_cr(tc, tr)
        if not nc:
            nc = "-"

        new_fen = self._grid_to_fen(new_grid)
        new_turn = "b" if self.turn == "w" else "w"
        new_fullmove = self.fullmove if new_turn == "w" else self.fullmove + 1
        return Board(f"{new_fen} {new_turn} {nc} {new_en_passant} 0 {new_fullmove}")

    def _grid_to_fen(self, grid) -> str:
        rows = []
        for row in grid:
            s, empty = "", 0
            for cell in row:
                if cell == EMPTY:
                    empty += 1
                else:
                    if empty:
                        s += str(empty)
                        empty = 0
                    s += cell
            if empty:
                s += str(empty)
            rows.append(s)
        return "/".join(rows)

    def to_display_grid(self) -> list:
        return [
            [PIECE_UNICODE.get(self.grid[r][c], " ") for c in range(8)]
            for r in range(8)
        ]


# ── helpers ───────────────────────────────────────────────────────────────────

def _uci_to_coords(uci: str):
    fc = ord(uci[0]) - ord("a")
    fr = 8 - int(uci[1])
    tc = ord(uci[2]) - ord("a")
    tr = 8 - int(uci[3])
    return fc, fr, tc, tr


def coords_to_uci(fc: int, fr: int, tc: int, tr: int) -> str:
    return chr(ord("a") + fc) + str(8 - fr) + chr(ord("a") + tc) + str(8 - tr)


def is_correct_move(puzzle: dict, move_index: int, uci: str) -> bool:
    solution = puzzle.get("solution", [])
    if move_index >= len(solution):
        return False
    return solution[move_index].lower() == uci.lower()


def get_opponent_reply(puzzle: dict, move_index: int):
    solution = puzzle.get("solution", [])
    reply_index = move_index + 1
    return solution[reply_index] if reply_index < len(solution) else None


def hint_squares(puzzle: dict, move_index: int):
    """Return ((fc,fr),(tc,tr)) for the expected move, or None."""
    solution = puzzle.get("solution", [])
    if move_index >= len(solution):
        return None
    uci = solution[move_index]
    fc, fr, tc, tr = _uci_to_coords(uci)
    return (fc, fr), (tc, tr)
