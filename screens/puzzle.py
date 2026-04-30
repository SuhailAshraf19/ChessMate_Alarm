"""
screens/puzzle.py — Interactive chess puzzle solver.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle, Ellipse, Line, RoundedRectangle
from kivy.clock import Clock
from kivy.app import App
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.logger import Logger
import threading

from utils.chess_engine import (
    Board, coords_to_uci, is_correct_move, get_opponent_reply, hint_squares, PIECE_UNICODE
)
from data.lichess_puzzles import (
    delete_puzzle,
    ensure_puzzle_buffer,
    get_puzzles_for_alarm,
    queue_puzzle_fetch,
)
from utils.android_alarm import stop_alarm_service

# ── colours ───────────────────────────────────────────────────────────────────
BG         = (0.07, 0.07, 0.10, 1)
LIGHT_SQ   = (0.88, 0.81, 0.67, 1)
DARK_SQ    = (0.48, 0.33, 0.22, 1)
SEL_LIGHT  = (0.46, 0.72, 0.36, 0.9)
SEL_DARK   = (0.34, 0.60, 0.24, 0.9)
LAST_SELF_LIGHT = (0.93, 0.91, 0.40, 0.82)
LAST_SELF_DARK  = (0.78, 0.76, 0.18, 0.82)
LAST_OPP_LIGHT  = (0.34, 0.70, 0.38, 0.82)
LAST_OPP_DARK   = (0.22, 0.56, 0.28, 0.82)
WRONG_CLR  = (0.85, 0.18, 0.18, 0.75)
AMBER      = (1.00, 0.76, 0.22, 1)
WHITE      = (0.95, 0.95, 0.97, 1)
GREY       = (0.55, 0.55, 0.60, 1)
GREEN      = (0.20, 0.78, 0.35, 1)
RED_C      = (0.90, 0.28, 0.28, 1)
DOT_CLR    = (0.10, 0.10, 0.10, 0.35)
CAP_CLR    = (0.10, 0.10, 0.10, 0.30)


# ─────────────────────────────────────────────────────────────────────────────
class ChessSquare(Button):

    def __init__(self, col: int, row: int, **kw):
        super().__init__(
            font_size="40sp", bold=True,
            font_name="ChessSymbols",
            background_normal="", background_color=(0, 0, 0, 0),
            border=(0, 0, 0, 0), **kw
        )
        self.col    = col
        self.row    = row
        self.piece_code = "."
        self._light = (col + row) % 2 == 0
        self._state = "normal"
        self._dot   = False
        self._cap   = False
        self._draw()
        self.bind(pos=self._draw, size=self._draw)

    def set_state(self, s):  self._state = s; self._draw()
    def set_dot(self, d, c=False): self._dot = d; self._cap = c; self._draw()

    def _draw(self, *_):
        self.font_size = max(dp(22), min(self.width, self.height) * 0.72)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*(LIGHT_SQ if self._light else DARK_SQ))
            Rectangle(pos=self.pos, size=self.size)

            if self._state == "selected":
                Color(*(SEL_LIGHT if self._light else SEL_DARK))
                Rectangle(pos=self.pos, size=self.size)
            elif self._state == "last_self":
                Color(*(LAST_SELF_LIGHT if self._light else LAST_SELF_DARK))
                Rectangle(pos=self.pos, size=self.size)
            elif self._state == "last_opponent":
                Color(*(LAST_OPP_LIGHT if self._light else LAST_OPP_DARK))
                Rectangle(pos=self.pos, size=self.size)
            elif self._state == "wrong":
                Color(*WRONG_CLR)
                Rectangle(pos=self.pos, size=self.size)
            elif self._state == "hint":
                Color(0.30, 0.60, 1.0, 0.55)
                Rectangle(pos=self.pos, size=self.size)

            if self._dot:
                r  = min(self.width, self.height) * 0.17
                cx = self.x + self.width  / 2
                cy = self.y + self.height / 2
                Color(*DOT_CLR)
                Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

            if self._cap:
                r  = min(self.width, self.height) * 0.46
                lw = max(2, min(self.width, self.height) * 0.10)
                cx = self.x + self.width  / 2
                cy = self.y + self.height / 2
                Color(*CAP_CLR)
                Line(circle=(cx, cy, r), width=lw)

        if self.piece_code != "." and self.piece_code.isupper():
            self.color = (0.92, 0.91, 0.86, 1)
        elif self.piece_code != "." and self.piece_code.islower():
            self.color = (0.06, 0.06, 0.06, 1)
        else:
            self.color = (0, 0, 0, 0)


# ─────────────────────────────────────────────────────────────────────────────
class ChessBoard(BoxLayout):

    def __init__(self, on_move_attempt, **kw):
        super().__init__(orientation="vertical", **kw)
        self._on_move       = on_move_attempt
        self._squares       = {}
        self._selected      = None
        self._legal_targets = []
        self._last_move_self = []
        self._last_move_opponent = []
        self._board         = None
        self._player_color  = "w"
        self._flipped       = False
        self._locked        = False

        # File labels row (a–h)
        gutter = dp(18)

        file_row = BoxLayout(size_hint_y=None, height=gutter)
        file_row.add_widget(Label(size_hint_x=None, width=gutter))
        for f in "abcdefgh":
            file_row.add_widget(
                Label(text=f, font_size="9sp", font_name="DejaVuSans",
                      color=GREY, halign="center", valign="middle")
            )

        # Rank labels + grid
        mid = BoxLayout(orientation="horizontal")
        rank_col = BoxLayout(orientation="vertical", size_hint_x=None, width=gutter)
        for rank in range(8, 0, -1):
            rank_col.add_widget(
                Label(text=str(rank), font_size="9sp", font_name="DejaVuSans",
                      color=GREY, halign="center", valign="middle")
            )

        grid = GridLayout(cols=8, rows=8, spacing=0)
        self._grid = grid
        for row in range(8):
            for col in range(8):
                sq = ChessSquare(col, row)
                sq.bind(on_release=self._on_tap)
                self._squares[(col, row)] = sq
                grid.add_widget(sq)

        mid.add_widget(rank_col)
        mid.add_widget(grid)
        self.add_widget(file_row)
        self.add_widget(mid)

    # ── public ────────────────────────────────────────────────────────────

    def load_position(self, board: Board, player_color: str):
        self._board        = board
        self._player_color = player_color
        # Show the side to move toward the user.
        self._flipped      = (player_color == "b")
        self._selected     = None
        self._legal_targets = []
        self._last_move_self = []
        self._last_move_opponent = []
        self._locked       = False
        self._render()

    def lock(self):   self._locked = True;  self._clear_sel()
    def unlock(self): self._locked = False

    def apply_move(self, uci: str, mover: str = "self"):
        if not self._board: return
        fc = ord(uci[0]) - ord("a"); fr = 8 - int(uci[1])
        tc = ord(uci[2]) - ord("a"); tr = 8 - int(uci[3])

        mover_key = "opponent" if mover == "opponent" else "self"
        
        # Convert board coords to display coords if flipped
        if self._flipped:
            fc, fr = 7 - fc, 7 - fr
            tc, tr = 7 - tc, 7 - tr
        
        self._board     = self._board.apply_uci(uci)
        if mover_key == "opponent":
            self._last_move_opponent = [(fc, fr), (tc, tr)]
        else:
            self._last_move_self = [(fc, fr), (tc, tr)]
        self._clear_sel()
        self._render()

    def flash_wrong(self, col, row):
        sq = self._squares.get((col, row))
        if sq:
            sq.set_state("wrong")
            Clock.schedule_once(lambda *_: sq.set_state("normal"), 0.55)

    def show_hint(self, coords):
        for (c, r) in coords:
            sq = self._squares.get((c, r))
            if sq: sq.set_state("hint")

    # ── internals ────────────────────────────────────────────────────────

    def _render(self):
        if not self._board: return
        grid   = self._board.to_display_grid()
        last_self = {(c, r) for c, r in self._last_move_self}
        last_opponent = {(c, r) for c, r in self._last_move_opponent}
        for (col, row), sq in self._squares.items():
            # Get actual indices from grid (accounting for board flip)
            actual_col = (7 - col) if self._flipped else col
            actual_row = (7 - row) if self._flipped else row
            sq.text   = grid[actual_row][actual_col]
            sq.piece_code = self._board.grid[actual_row][actual_col]
            sq._dot   = False
            sq._cap   = False
            if (col, row) in last_self:
                sq._state = "last_self"
            elif (col, row) in last_opponent:
                sq._state = "last_opponent"
            else:
                sq._state = "normal"
            sq._draw()

    def _render_optimized(self, uci: str):
        """Optimized render - only update affected squares for faster response."""
        if not self._board or len(uci) < 4: 
            self._render()
            return
        
        grid = self._board.to_display_grid()
        last_self = {(c, r) for c, r in self._last_move_self}
        last_opponent = {(c, r) for c, r in self._last_move_opponent}
        
        # Parse move coordinates
        fc = ord(uci[0]) - ord("a")
        fr = 8 - int(uci[1])
        tc = ord(uci[2]) - ord("a")
        tr = 8 - int(uci[3])
        
        # Convert to display coords if flipped
        if self._flipped:
            fc, fr = 7 - fc, 7 - fr
            tc, tr = 7 - tc, 7 - tr
        
        # Only update the affected squares (from, to, and en passant capture if applicable)
        affected = {(fc, fr), (tc, tr)}

        for coord in affected:
            sq = self._squares.get(coord)
            if not sq:
                continue
            
            # Get board coordinates
            board_col = (7 - coord[0]) if self._flipped else coord[0]
            board_row = (7 - coord[1]) if self._flipped else coord[1]
            
            sq.text = PIECE_UNICODE.get(grid[board_row][board_col], grid[board_row][board_col])
            sq.piece_code = self._board.grid[board_row][board_col]
            sq._dot = False
            sq._cap = False
            if coord in last_self:
                sq._state = "last_self"
            elif coord in last_opponent:
                sq._state = "last_opponent"
            else:
                sq._state = "normal"
            sq._draw()
        self._clear_sel()

    def _clear_sel(self):
        if self._selected:
            sc, sr, sbc, sbr = self._selected
            sq = self._squares.get((sc, sr))
            if sq:
                sq.set_state("normal")
        for (c, r) in self._legal_targets:
            sq = self._squares.get((c, r))
            if sq: sq.set_dot(False, False)
        self._selected      = None
        self._legal_targets = []

    def _on_tap(self, sq: ChessSquare):
        if self._locked or not self._board: return

        # Convert display coords to actual board coords if flipped
        board_col = (7 - sq.col) if self._flipped else sq.col
        board_row = (7 - sq.row) if self._flipped else sq.row

        piece  = self._board.piece_at(board_col, board_row)
        # ── determine ownership based on player_color ─────────────────────
        is_own = (
            (piece.isupper() and self._player_color == "w") or
            (piece.islower() and self._player_color == "b")
        )

        if self._selected is None:
            if piece != "." and is_own:
                self._do_select(sq, board_col, board_row)
        else:
            sc, sr, sbc, sbr = self._selected
            if (sc, sr) == (sq.col, sq.row):
                self._clear_sel(); return
            if piece != "." and is_own:
                self._clear_sel(); self._do_select(sq, board_col, board_row); return
            # Attempt move
            uci = coords_to_uci(sbc, sbr, board_col, board_row)
            self._clear_sel()
            self._on_move(uci, sq.col, sq.row)

    def _do_select(self, sq: ChessSquare, board_col: int, board_row: int):
        self._selected = (sq.col, sq.row, board_col, board_row)
        legal = self._board.legal_moves_from(board_col, board_row)
        self._legal_targets = [
            ((7 - bc, 7 - br) if self._flipped else (bc, br))
            for bc, br in legal
        ]
        for (board_tc, board_tr), (display_tc, display_tr) in zip(legal, self._legal_targets):
            tsq = self._squares[(display_tc, display_tr)]
            if self._board.piece_at(board_tc, board_tr) == ".":
                tsq.set_dot(True, False)
            else:
                tsq.set_dot(False, True)


# ─────────────────────────────────────────────────────────────────────────────
class ScoreFlash(Label):
    def show(self, delta: int):
        self.text    = f"+{delta}" if delta > 0 else str(delta)
        self.color   = (*GREEN[:3], 1) if delta > 0 else (*RED_C[:3], 1)
        self.opacity = 1.0
        Animation(opacity=0, duration=1.6).start(self)


# ─────────────────────────────────────────────────────────────────────────────
class PuzzleScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._puzzles          = []
        self._current_idx      = 0
        self._move_idx         = 0
        self._alarm            = None
        self._player_score     = 1200
        self._solved_count     = 0
        self._required_count   = 3
        self._had_mistake      = False   # has player made ANY wrong move this puzzle?
        self._penalty_applied  = False   # has the puzzle penalty already been applied?
        self._target_rating    = 1200
        self._free_solve_mode  = False
        self._board_wrap       = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)

        # ── top bar ───────────────────────────────────────────────────────
        top = BoxLayout(orientation="vertical", size_hint_y=None, height="102dp",
                        padding=["12dp","6dp","12dp","4dp"], spacing="3dp")
        with top.canvas.before:
            Color(0.09, 0.09, 0.13, 1)
            top._bg = Rectangle(pos=top.pos, size=top.size)
        top.bind(pos=lambda w,_: setattr(w._bg,'pos',w.pos),
                 size=lambda w,_: setattr(w._bg,'size',w.size))

        # Row 1
        r1 = BoxLayout(orientation="horizontal", size_hint_y=None, height="22dp")
        self.back_btn = Button(
            text="Back", font_size="12sp", font_name="DejaVuSans",
            size_hint_x=None, width="54dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=AMBER, opacity=0, disabled=True
        )
        self.back_btn.bind(on_release=lambda *_: self._go_back())
        self.progress_label = Label(
            text="Puzzle 1 / 3", font_size="13sp", font_name="DejaVuSans", color=AMBER,
            size_hint_x=0.30, halign="left", valign="middle"
        )
        self.progress_label.bind(size=self.progress_label.setter("text_size"))

        self.score_label = Label(
            text="Rating: 1200", font_size="12sp", font_name="DejaVuSans", color=WHITE,
            size_hint_x=0.38, halign="center", valign="middle"
        )
        self.score_label.bind(size=self.score_label.setter("text_size"))

        self.source_label = Label(
            text="", font_size="10sp", font_name="DejaVuSans", color=GREY,
            size_hint_x=0.32, halign="right", valign="middle"
        )
        self.source_label.bind(size=self.source_label.setter("text_size"))
        r1.add_widget(self.back_btn)
        r1.add_widget(self.progress_label)
        r1.add_widget(self.score_label)
        r1.add_widget(self.source_label)

        # Row 2: progress bar
        self.progress_bar = ProgressBar(max=100, value=0,
                                        size_hint_y=None, height="5dp")

        # Row 3: status
        self.puzzle_status = Label(
            text="Find the best move!", font_size="14sp", bold=True,
            font_name="DejaVuSans", color=WHITE,
            size_hint_y=None, height="24dp", halign="center"
        )
        self.puzzle_status.bind(size=self.puzzle_status.setter("text_size"))

        # Row 4: turn indicator + score flash
        r4 = BoxLayout(orientation="horizontal", size_hint_y=None, height="22dp")
        self.turn_label = Label(
            text="", font_size="13sp", font_name="DejaVuSans",
            color=WHITE, size_hint_x=0.6, halign="left", valign="middle"
        )
        self.turn_label.bind(size=self.turn_label.setter("text_size"))
        self.score_flash = ScoreFlash(
            text="", font_size="14sp", bold=True, font_name="DejaVuSans",
            opacity=0, size_hint_x=0.4, halign="right", valign="middle"
        )
        self.score_flash.bind(size=self.score_flash.setter("text_size"))
        r4.add_widget(self.turn_label)
        r4.add_widget(self.score_flash)

        top.add_widget(r1)
        top.add_widget(self.progress_bar)
        top.add_widget(self.puzzle_status)
        top.add_widget(r4)

        # ── board ─────────────────────────────────────────────────────────
        board_wrap = AnchorLayout(
            anchor_x="center",
            anchor_y="center",
            padding="8dp",
        )
        self._board_wrap = board_wrap
        self.board = ChessBoard(on_move_attempt=self._on_move_attempt)
        self.board.size_hint = (None, None)
        board_wrap.add_widget(self.board)
        board_wrap.bind(size=self._resize_board)

        # ── bottom bar ────────────────────────────────────────────────────
        bottom = BoxLayout(orientation="horizontal", size_hint_y=None, height="56dp",
                           padding="10dp", spacing="8dp")
        with bottom.canvas.before:
            Color(0.09, 0.09, 0.13, 1)
            bottom._bg = Rectangle(pos=bottom.pos, size=bottom.size)
        bottom.bind(pos=lambda w,_: setattr(w._bg,'pos',w.pos),
                    size=lambda w,_: setattr(w._bg,'size',w.size))

        hint_btn = Button(
            text="Hint", font_size="14sp", font_name="DejaVuSans",
            background_normal="", background_color=(0,0,0,0),
            color=AMBER, size_hint_x=0.22
        )
        hint_btn.bind(on_release=lambda *_: self._show_hint())

        self.theme_label = Label(
            text="", font_size="11sp", font_name="DejaVuSans", color=GREY,
            size_hint_x=0.46,
            halign="center", valign="middle"
        )
        self.theme_label.bind(size=self.theme_label.setter("text_size"))

        skip_btn = Button(
            text="Skip (-15)", font_size="13sp", font_name="DejaVuSans",
            background_normal="", background_color=(0,0,0,0),
            color=(0.90, 0.40, 0.40, 1), size_hint_x=0.32
        )
        skip_btn.bind(on_release=lambda *_: self._skip_puzzle())
        self.skip_btn = skip_btn

        bottom.add_widget(hint_btn)
        bottom.add_widget(self.theme_label)
        bottom.add_widget(skip_btn)

        root.add_widget(top)
        root.add_widget(board_wrap)
        root.add_widget(bottom)
        self.add_widget(root)
        Clock.schedule_once(self._resize_board, 0)

    # ── session control ───────────────────────────────────────────────────

    def start_session(self, alarm, player_score=1200, count=3):
        self._alarm            = alarm
        self._player_score     = player_score
        self._required_count   = count
        self._free_solve_mode  = (count is None)
        self._solved_count     = 0
        self._current_idx      = 0
        self._puzzles          = []
        self._move_idx         = 0
        self._had_mistake      = False
        self._penalty_applied  = False

        self._update_score_label()
        self._refresh_skip_label()
        self._sync_back_button()
        self.puzzle_status.text  = "Loading live Lichess puzzles..."
        self.puzzle_status.color = WHITE
        self.turn_label.text     = ""
        self.board.lock()

        try:
            if alarm and isinstance(alarm, dict) and int(alarm.get("id", 0)) > 0:
                app = App.get_running_app()
                app.store.set_active_alarm(alarm)
                if hasattr(app, "scheduler"):
                    app.scheduler.set_active(alarm)
        except Exception:
            Logger.exception("PuzzleScreen: failed to persist active alarm on session start")

        def _fetch():
            app = App.get_running_app()
            self._target_rating = app.store.get_score()
            ensure_puzzle_buffer(self._target_rating, 50)
            wanted = 50 if count is None else max(50, count)
            puzzles = get_puzzles_for_alarm(
                self._target_rating,
                wanted,
                allow_repeat_last=False,
            )
            Clock.schedule_once(lambda *_: self._on_loaded(puzzles), 0)

        threading.Thread(target=_fetch, daemon=True).start()

    def _resize_board(self, *_):
        if not self._board_wrap:
            return
        side = max(0, min(self._board_wrap.width - dp(16), self._board_wrap.height - dp(16)))
        self.board.size = (side, side)

    def _on_loaded(self, puzzles):
        self._puzzles = puzzles
        if puzzles:
            self._refresh_skip_label()
            self._load_puzzle(0)
        else:
            self.puzzle_status.text = "Error loading puzzles. Retrying..."
            Clock.schedule_once(lambda *_: self._retry(), 3)

    def _retry(self):
        app = App.get_running_app()
        s   = app.store.get_settings()
        self.start_session(self._alarm, self._player_score, self._required_count)

    def _load_puzzle(self, idx: int):
        if idx >= len(self._puzzles):
            self._fetch_more(then_idx=idx)
            return

        self._current_idx     = idx
        self._move_idx        = 0
        self._had_mistake     = False
        self._penalty_applied = False
        puzzle = self._puzzles[idx]

        self.progress_label.text = (
            "Free Solve"
            if self._required_count is None
            else f"Puzzle {self._solved_count + 1} / {self._required_count}"
        )
        self.progress_bar.value = 0 if self._required_count is None else int(
            self._solved_count / self._required_count * 100
        )
        self._refresh_skip_label()

        src_map = {"lichess": "Lichess Live", "cache": "Lichess (cached)"}
        self.source_label.text = src_map.get(puzzle.get("source", "cache"), "Lichess (cached)")

        themes = puzzle.get("themes", [])
        self.theme_label.text = "  ".join(themes[:3]) if themes else ""

        rating = puzzle.get("rating", "?")
        self.puzzle_status.text  = f"Find the best move!  (Rating: {rating})"
        self.puzzle_status.color = WHITE

        fen          = puzzle["fen"]
        parts        = fen.split()
        fen_turn     = parts[1] if len(parts) > 1 else "w"
        player_color = "b" if fen_turn == "w" else "w"
        board_preview = Board(fen)
        solution      = puzzle.get("solution", [])
        self._set_turn_label(player_color)

        self.board.load_position(board_preview, player_color)
        if solution:
            first_move = str(solution[0])
            if len(first_move) >= 4:
                self.board.apply_move(first_move, mover="self")
                self._move_idx = 1
                if self.board._board:
                    self._set_turn_label(player_color)
                if len(solution) <= 1:
                    Clock.schedule_once(lambda *_: self._puzzle_solved(), 0.4)
        self.board.unlock()
        self._reset_status()

    # ── move handling ─────────────────────────────────────────────────────

    def _on_move_attempt(self, uci: str, to_col: int, to_row: int):
        try:
            if not self._puzzles:
                return
            puzzle  = self._puzzles[self._current_idx]

            # Check if this move might be a promotion
            from_col = ord(uci[0]) - ord("a")
            from_row = 8 - int(uci[1])
            to_col_actual = ord(uci[2]) - ord("a")
            to_row_actual = 8 - int(uci[3])

            piece = self.board._board.piece_at(from_col, from_row)

            # If it's a pawn reaching the last rank, check if promotion is expected
            if piece.upper() == "P" and (to_row_actual == 0 or to_row_actual == 7):
                solution = puzzle.get("solution", [])
                if self._move_idx < len(solution):
                    expected = solution[self._move_idx]
                    # If expected move is 5 chars (promotion), append promotion piece to uci
                    if len(expected) == 5:
                        uci = uci[:4] + expected[4]

            correct = is_correct_move(puzzle, self._move_idx, uci)

            if correct:
                # Check if move is a capture (there's a piece at destination)
                is_capture = self.board._board.piece_at(to_col_actual, to_row_actual) != "."

                self.board.apply_move(uci, mover="self")
                self._play_move_sound(is_capture)
                self._move_idx          += 1
                self.puzzle_status.text  = "Correct!"
                self.puzzle_status.color = GREEN

                if self._move_idx >= len(puzzle["solution"]):
                    Clock.schedule_once(lambda *_: self._puzzle_solved(), 0.7)
                    return

                reply = get_opponent_reply(puzzle, self._move_idx - 1)
                if reply:
                    self.board.lock()
                    Clock.schedule_once(lambda *_: self._engine_reply(reply), 0.9)
            else:
                self.board.flash_wrong(to_col, to_row)
                self._had_mistake = True

                # Deduct score only on the FIRST wrong move of this puzzle
                if not self._penalty_applied:
                    self._penalty_applied = True
                    app   = App.get_running_app()
                    delta = app.store.record_first_wrong_move(int(puzzle.get("rating", 1500)))
                    self._update_score_label()
                    self._refresh_skip_label()
                    self.score_flash.show(delta)

                self.puzzle_status.text  = "Not quite - try again!"
                self.puzzle_status.color = RED_C
                Clock.schedule_once(lambda *_: self._reset_status(), 1.2)
        except Exception:
            Logger.exception("PuzzleScreen: move attempt failed")
            self.puzzle_status.text = "Move error - try again"
            self.puzzle_status.color = RED_C
            Clock.schedule_once(lambda *_: self._reset_status(), 1.0)

    def _puzzle_solved(self):
        app   = App.get_running_app()
        puzzle = self._puzzles[self._current_idx]
        delta = app.store.record_puzzle_solved(
            int(puzzle.get("rating", 1500)),
            had_mistakes=self._had_mistake,
        )
        delete_puzzle(str(puzzle.get("id", "")), target_rating=app.store.get_score())
        self._update_score_label()
        self._refresh_skip_label()
        if delta:
            self.score_flash.show(delta)

        if self._puzzles:
            self._puzzles.pop(0)

        self._top_up_from_cache()

        self._solved_count += 1
        if self._required_count is not None:
            self.progress_bar.value = int(
                self._solved_count / self._required_count * 100
            )

        if self._required_count is not None and self._solved_count >= self._required_count:
            self._all_solved()
            return

        if not self._puzzles:
            if self._refill_from_cache_or_bundle(count=20, reload_if_empty=True):
                self.puzzle_status.text = "Loading next puzzle..."
                self.puzzle_status.color = GREEN
            else:
                self.puzzle_status.text = "Fetching more puzzles..."
                self.puzzle_status.color = WHITE
                self._queue_replacement(reload_if_empty=True)
            return

        if self._required_count is None:
            self.puzzle_status.text = "Solved! Loading next puzzle..."
        else:
            remaining = self._required_count - self._solved_count
            self.puzzle_status.text = f"Solved! {remaining} more to go..."
        self.puzzle_status.color = GREEN
        Clock.schedule_once(
            lambda *_: self._load_puzzle(0), 1.2
        )

    def _skip_puzzle(self):
        if not self._puzzles:
            return
        app   = App.get_running_app()
        puzzle = self._puzzles[self._current_idx]
        delta = app.store.record_puzzle_skipped(int(puzzle.get("rating", 1500)))
        self._update_score_label()
        self._refresh_skip_label()
        self.score_flash.show(delta)

        self.puzzle_status.text  = f"Skipped  ({delta})"
        self.puzzle_status.color = RED_C

        if self._puzzles:
            self._puzzles.pop(0)

        self._top_up_from_cache()

        if self._puzzles:
            self.puzzle_status.text = "Loading next puzzle..."
            Clock.schedule_once(lambda *_: self._load_puzzle(0), 0.2)
        else:
            if self._refill_from_cache_or_bundle(count=20, reload_if_empty=True):
                self.puzzle_status.text = "Loading next puzzle..."
                self.puzzle_status.color = GREEN
            else:
                self.puzzle_status.text = "Fetching next puzzle..."
                self._queue_replacement(reload_if_empty=True)

    def _engine_reply(self, uci: str):
        try:
            if self.board._board and len(uci) >= 4:
                to_col = ord(uci[2]) - ord("a")
                to_row = 8 - int(uci[3])
                is_capture = self.board._board.piece_at(to_col, to_row) != "."
            else:
                is_capture = False
            self.board.apply_move(uci, mover="opponent")
            self._play_move_sound(is_capture)
            self._move_idx += 1
            self.board.unlock()
            if self.board._board:
                # Keep the label on the human-controlled side, not the auto-reply side.
                self._set_turn_label(self._player_color)
            puzzle = self._puzzles[self._current_idx]
            if self._move_idx >= len(puzzle["solution"]):
                Clock.schedule_once(lambda *_: self._puzzle_solved(), 0.4)
            else:
                self._reset_status()
        except Exception:
            Logger.exception("PuzzleScreen: engine reply failed")
            self.board.unlock()
            self._reset_status()

    # ── fetch more ────────────────────────────────────────────────────────

    def _fetch_more(self, then_idx=None):
        self._queue_replacement(reload_if_empty=then_idx is not None)

    def _append(self, more, then_idx=None):
        if more:
            self._puzzles.extend(more)
        if then_idx is not None and then_idx < len(self._puzzles):
            self._load_puzzle(0)
            return

    def _queue_ids(self):
        return [
            str(p.get("id", ""))
            for p in self._puzzles
            if p and p.get("id")
        ]

    def _top_up_from_cache(self, floor: int = 30, target: int = 50):
        if len(self._puzzles) >= floor:
            return
        need = max(0, int(target) - len(self._puzzles))
        if need <= 0:
            return
        cached = get_puzzles_for_alarm(
            self._target_rating,
            need,
            allow_repeat_last=False,
            exclude_ids=set(self._queue_ids()),
        )
        if cached:
            self._puzzles.extend(cached)
            Logger.info(
                f"PuzzleScreen: topped_up_from_cache added={len(cached)} total={len(self._puzzles)} floor={floor} target={target}"
            )

    def _refill_from_cache_or_bundle(self, count: int = 20, reload_if_empty: bool = True):
        cached = get_puzzles_for_alarm(
            self._target_rating,
            count,
            allow_repeat_last=False,
            exclude_ids=set(self._queue_ids()),
        )
        if cached:
            self._puzzles.extend(cached)
            Logger.info(
                f"PuzzleScreen: refill_from_cache_or_bundle added={len(cached)} total={len(self._puzzles)}"
            )
            if reload_if_empty and self._puzzles:
                self._load_puzzle(0)
            return True
        return False

    def _fetch_replacement(self):
        self._queue_replacement()

    def _queue_replacement(self, reload_if_empty: bool = False):
        current_score = App.get_running_app().store.get_score()
        self._target_rating = current_score

        def _on_ready(puzzle):
            if not puzzle:
                return

            def _append_once(*_):
                self._puzzles.append(dict(puzzle))
                if reload_if_empty and len(self._puzzles) == 1:
                    self._load_puzzle(0)

            Clock.schedule_once(_append_once, 0)

        queue_puzzle_fetch(
            current_score,
            callback=_on_ready,
            exclude_ids=set(self._queue_ids()),
        )

    # ── finish ────────────────────────────────────────────────────────────

    def _all_solved(self):
        self.progress_bar.value  = 100
        self.puzzle_status.text  = "All puzzles solved! Alarm dismissed!"
        self.puzzle_status.color = GREEN
        self.turn_label.text     = ""
        self.board.lock()
        
        # Stop the alarm sound
        app = App.get_running_app()
        try:
            alarm = getattr(self, "_alarm", None)
            alarm_id = int(alarm.get("id", 0)) if isinstance(alarm, dict) else 0
            if alarm_id:
                stop_alarm_service(alarm_id)
                from jnius import autoclass

                AlarmRinger = autoclass("org.chessmate.chessmatesalarm.AlarmRinger")
                AlarmRinger.stop()
        except Exception:
            pass
        if hasattr(app, "sound_preview"):
            app.sound_preview.stop()
        
        # Clear snooze metadata and disable one-time alarms
        try:
            alarm = getattr(self, "_alarm", None)
            if alarm and isinstance(alarm, dict):
                # Clear snoozed state
                app.store.update_alarm(alarm["id"], {"snoozed_until": None, "snooze_count": 0})
                # If it was a one-time alarm (no days), disable it now
                if not alarm.get("days"):
                    app.store.update_alarm(alarm["id"], {"enabled": False})
        except Exception:
            pass

        try:
            app.store.clear_active_alarm()
        except Exception:
            pass
        app.scheduler.clear_active()
        Clock.schedule_once(
            lambda *_: setattr(self.manager, "current", "home"), 2.5
        )

    # ── hint ─────────────────────────────────────────────────────────────

    def _show_hint(self):
        if not self._puzzles:
            return
        coords = hint_squares(self._puzzles[self._current_idx], self._move_idx)
        if coords:
            if not self._penalty_applied:
                app = App.get_running_app()
                puzzle = self._puzzles[self._current_idx]
                delta = app.store.record_puzzle_hint(int(puzzle.get("rating", 1500)))
                self._update_score_label()
                self._refresh_skip_label()
                self.score_flash.show(delta)
                self._penalty_applied = True
            self._had_mistake = True
            (fc, fr), (tc, tr) = coords
            # Convert board coords to display coords if board is flipped
            if self.board._flipped:
                fc, fr = 7 - fc, 7 - fr
                tc, tr = 7 - tc, 7 - tr
            self.board.show_hint([(fc, fr), (tc, tr)])
            self.puzzle_status.text  = "Hint: move the highlighted piece"
            self.puzzle_status.color = AMBER

    # ── helpers ───────────────────────────────────────────────────────────

    def _reset_status(self):
        self.puzzle_status.text  = "Find the best move!"
        self.puzzle_status.color = WHITE

    def _update_score_label(self):
        score = App.get_running_app().store.get_score()
        self.score_label.text = f"Rating: {score}"

    def _refresh_skip_label(self):
        try:
            app = App.get_running_app()
            if not app or not hasattr(app, "store"):
                return
            if self._puzzles and 0 <= self._current_idx < len(self._puzzles):
                puzzle_rating = int(self._puzzles[self._current_idx].get("rating", 1500))
            elif self._puzzles:
                puzzle_rating = int(self._puzzles[0].get("rating", 1500))
            else:
                puzzle_rating = 1500
            delta = app.store.preview_puzzle_skip_delta(puzzle_rating)
            if hasattr(self, "skip_btn") and self.skip_btn:
                self.skip_btn.text = f"Skip ({delta})"
        except Exception:
            Logger.exception("PuzzleScreen: failed to refresh skip label")

    def _play_move_sound(self, is_capture: bool):
        app = App.get_running_app()
        volume = app.store.get_setting("volume", 80)
        filename = "capture.wav" if is_capture else "move.wav"
        if hasattr(app, "sound_preview"):
            try:
                app.sound_preview.play_effect(filename, volume=volume)
            except Exception:
                Logger.exception("PuzzleScreen: move sound failed")

    def _set_turn_label(self, actual_color: str):
        if actual_color == "w":
            self.turn_label.text = "White to move"
            self.turn_label.color = (0.97, 0.97, 0.97, 1)
        else:
            self.turn_label.text = "Black to move"
            self.turn_label.color = (0.75, 0.75, 0.75, 1)

    def _sync_back_button(self):
        self.back_btn.opacity = 1 if self._free_solve_mode else 0
        self.back_btn.disabled = not self._free_solve_mode

    def _go_back(self):
        self.board.lock()
        self.manager.current = "home"
