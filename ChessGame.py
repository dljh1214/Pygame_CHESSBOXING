import pygame
import sys
import chess
from stockfish import Stockfish


class ChessGUI:
    # === 클래스 상수들 ===
    WINDOW_SIZE = 640
    BOARD_SIZE = 8
    FPS = 60

    LIGHT_SQ = (240, 217, 181)
    DARK_SQ = (181, 136, 99)
    HIGHLIGHT = (186, 202, 68)
    BLACK = (30, 30, 30)

    HUMAN_COLOR = chess.WHITE
    AI_COLOR = chess.BLACK

    STOCKFISH_PATH = r"stockfish/stockfish-windows-x86-64-avx2.exe"

    PIECE_IMAGES = {
        "P": "images/piece/white_pawn.png",
        "p": "images/piece/black_pawn.png",
        "R": "images/piece/white_rook.png",
        "r": "images/piece/black_rook.png",
        "N": "images/piece/white_knight.png",
        "n": "images/piece/black_knight.png",
        "B": "images/piece/white_bishop.png",
        "b": "images/piece/black_bishop.png",
        "K": "images/piece/white_king.png",
        "k": "images/piece/black_king.png",
        "Q": "images/piece/white_queen.png",
        "q": "images/piece/black_queen.png",
    }

    def __init__(self, round_time, move_time, debuff=None, board=None):
        """
        round_time: 이번 체스 라운드 전체 제한 시간(초)
        move_time : 한 수당 기본 제한 시간(초)
        debuff    : 이번 라운드에만 적용되는 디버프 dict (없으면 None)
            예시:
            {
                "move_time_factor": 0.5,          # 사람 수당 초 50%로 감소
                "blind_side": "right",            # 'left' or 'right' 중 하나
                "hide_enemy_pieces": True,        # 상대 말 ? 처리
                # 또는 "hide_all_pieces": True 로 모두 ? 처리
            }
        board     : 이어서 진행할 chess.Board (없으면 새 게임 시작)
        """
        pygame.init()
        self.screen = pygame.display.set_mode((self.WINDOW_SIZE, self.WINDOW_SIZE))
        pygame.display.set_caption("Chess Round")
        self.clock = pygame.time.Clock()

        self.sq_size = self.WINDOW_SIZE // self.BOARD_SIZE

        # 말 이미지 로드
        self.piece_surfaces = {}
        for sym, path in self.PIECE_IMAGES.items():
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (self.sq_size, self.sq_size))
            self.piece_surfaces[sym] = img

        # 폰트 (기물 '?'용, HUD용)
        self.piece_font = pygame.font.SysFont("consolas", 28, bold=True)
        self.hud_font = pygame.font.SysFont("malgungothic", 20)

        # 체스 보드 (이어하기 지원)
        self.board = board if board is not None else chess.Board()

        # Stockfish 엔진
        self.engine = Stockfish(
            path=self.STOCKFISH_PATH,
            depth=12,
            parameters={"Threads": 2, "Hash": 256},
        )
        self.engine.set_depth(10)

        # 디버프 설정
        self.debuff = debuff or {}
        # 사람에게만 적용되는 한 수당 시간 감소
        self.human_move_time_limit = move_time * self.debuff.get("move_time_factor", 1.0)
        if self.human_move_time_limit <= 0:
            self.human_move_time_limit = 0.1  # 최소값 안전장치

        # 라운드 전체 시간 (디버프로 줄이고 싶으면 여기서 factor 추가)
        self.round_time_limit = round_time * self.debuff.get("round_time_factor", 1.0)

        # AI는 기본 move_time 그대로 사용 (원하면 별도 factor 줄 수 있음)
        self.ai_move_time_limit = move_time

        self.selected_square = None  # (col, row) or None

    # -----------------------------
    # 유틸 함수들
    # -----------------------------
    def square_from_mouse(self, pos):
        x, y = pos
        col = x // self.sq_size
        row = y // self.sq_size
        return col, row

    def square_to_uci(self, col, row):
        file_char = chr(ord("a") + col)
        rank_char = str(8 - row)
        return file_char + rank_char

    def is_human_turn(self):
        return self.board.turn == self.HUMAN_COLOR

    def make_ai_move(self):
        if self.board.is_game_over():
            return
        self.engine.set_fen_position(self.board.fen())
        best_move_uci = self.engine.get_best_move()
        if best_move_uci is None:
            return
        move = chess.Move.from_uci(best_move_uci)
        if move in self.board.legal_moves:
            self.board.push(move)

    # -----------------------------
    # 그리기 관련
    # -----------------------------
    def draw_board(self):
        for row in range(8):
            for col in range(8):
                color = self.LIGHT_SQ if (row + col) % 2 == 0 else self.DARK_SQ
                rect = pygame.Rect(
                    col * self.sq_size, row * self.sq_size, self.sq_size, self.sq_size
                )
                pygame.draw.rect(self.screen, color, rect)

                # 선택된 칸 하이라이트
                if self.selected_square is not None:
                    sel_c, sel_r = self.selected_square
                    if sel_c == col and sel_r == row:
                        pygame.draw.rect(self.screen, self.HIGHLIGHT, rect, 4)

                # 해당 칸의 기물
                square_index = chess.square(col, 7 - row)
                piece = self.board.piece_at(square_index)
                if not piece:
                    continue

                symbol = piece.symbol()  # 'P','p',...
                # 디버프: 말 물음표 처리
                hide_all = self.debuff.get("hide_all_pieces", False)
                hide_enemy = self.debuff.get("hide_enemy_pieces", False)

                if hide_all or (hide_enemy and piece.color != self.HUMAN_COLOR):
                    # '?' 문자로 표시
                    text_surf = self.piece_font.render("?", True, (0, 0, 0))
                    text_rect = text_surf.get_rect(center=rect.center)
                    self.screen.blit(text_surf, text_rect)
                else:
                    img = self.piece_surfaces.get(symbol)
                    if img:
                        self.screen.blit(img, rect)

        # 디버프: 시야 일부 가리기 (overlay)
        self.apply_vision_debuff()

    def apply_vision_debuff(self):
        """
        blind_side 디버프 적용:
        - 'left'  : 왼쪽 절반 가림
        - 'right' : 오른쪽 절반 가림
        """
        side = self.debuff.get("blind_side", None)
        if side not in ("left", "right"):
            return

        overlay = pygame.Surface((self.WINDOW_SIZE // 2, self.WINDOW_SIZE), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))  # 반투명 검은색

        if side == "left":
            self.screen.blit(overlay, (0, 0))
        else:  # right
            self.screen.blit(overlay, (self.WINDOW_SIZE // 2, 0))

    def draw_hud(self, round_timer, human_timer, ai_timer):
        # 남은 시간 텍스트
        round_txt = self.hud_font.render(f"라운드 남은 시간: {round_timer:5.1f}s", True, (255, 255, 255))
        human_txt = self.hud_font.render(f"플레이어 수당: {human_timer:4.1f}s", True, (255, 255, 255))
        ai_txt = self.hud_font.render(f"AI 수당: {ai_timer:4.1f}s", True, (255, 255, 255))

        self.screen.blit(round_txt, (10, 5))
        self.screen.blit(human_txt, (10, 30))
        self.screen.blit(ai_txt, (10, 55))

        # 활성 디버프 표시
        debuff_msgs = []
        if self.debuff.get("move_time_factor", 1.0) < 1.0:
            debuff_msgs.append("수당 시간 감소")
        if self.debuff.get("blind_side"):
            side = "좌측" if self.debuff["blind_side"] == "left" else "우측"
            debuff_msgs.append(f"{side} 시야 가림")
        if self.debuff.get("hide_enemy_pieces"):
            debuff_msgs.append("상대 말 ? 처리")
        if self.debuff.get("hide_all_pieces"):
            debuff_msgs.append("모든 말 ? 처리")

        if debuff_msgs:
            text = "디버프: " + ", ".join(debuff_msgs)
            debuff_txt = self.hud_font.render(text, True, (255, 200, 0))
            self.screen.blit(debuff_txt, (10, self.WINDOW_SIZE - 30))

    # -----------------------------
    # 메인 루프
    # -----------------------------
    def run(self):
        """
        체스 라운드를 진행하고 끝나면 dict로 결과 반환.
        언제 끝나든 현재 self.board를 함께 돌려줌.

        반환 예:
        {
            "game_over": True/False,          # 체스 경기 자체 종료 여부
            "result": "timeout_white" | "timeout_black"
                      | "checkmate_or_draw" | "round_timeout",
            "winner": "white" | "black" | None,
            "board": self.board
        }
        """
        running = True

        # 타이머 초기값
        round_timer = self.round_time_limit
        human_move_timer = self.human_move_time_limit
        ai_move_timer = self.ai_move_time_limit

        while running:
            dt = self.clock.tick(self.FPS) / 1000.0

            # --- 턴에 따른 타이머 감소 ---
            # 라운드 전체 시간은 항상 줄어듦
            round_timer -= dt

            if self.board.turn == self.HUMAN_COLOR:
                human_move_timer -= dt
                # ⛔ 사람 수당 초 초과 → 즉시 인간 패배
                if human_move_timer <= 0:
                    return {
                        "game_over": True,
                        "result": "timeout_white",
                        "winner": "black",
                        "board": self.board,
                    }
            else:
                ai_move_timer -= dt
                # ⛔ AI 수당 초 초과 → 즉시 AI 패배
                if ai_move_timer <= 0:
                    return {
                        "game_over": True,
                        "result": "timeout_black",
                        "winner": "white",
                        "board": self.board,
                    }

            # 라운드 전체 시간 초과 → 라운드만 종료 (체스 승패 X)
            if round_timer <= 0:
                return {
                    "game_over": False,
                    "result": "round_timeout",
                    "winner": None,
                    "board": self.board,
                }

            # 이벤트 처리
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and self.is_human_turn()
                    and not self.board.is_game_over()
                ):
                    col, row = self.square_from_mouse(event.pos)

                    if self.selected_square is None:
                        # 첫 클릭: 말 선택
                        sq = chess.square(col, 7 - row)
                        piece = self.board.piece_at(sq)
                        if piece and piece.color == self.HUMAN_COLOR:
                            self.selected_square = (col, row)
                    else:
                        # 두 번째 클릭: 이동 시도
                        src_c, src_r = self.selected_square
                        dst_c, dst_r = col, row

                        src_uci = self.square_to_uci(src_c, src_r)
                        dst_uci = self.square_to_uci(dst_c, dst_r)

                        src_sq = chess.square(src_c, 7 - src_r)
                        piece = self.board.piece_at(src_sq)
                        move = None

                        # 프로모션 처리
                        if piece and piece.piece_type == chess.PAWN:
                            if (
                                piece.color == chess.WHITE
                                and dst_r == 0
                            ) or (
                                piece.color == chess.BLACK
                                and dst_r == 7
                            ):
                                move = chess.Move.from_uci(src_uci + dst_uci + "q")

                        if move is None:
                            move = chess.Move.from_uci(src_uci + dst_uci)

                        if move in self.board.legal_moves:
                            self.board.push(move)
                            self.selected_square = None
                            # 사람 수를 두었으니 사람 move timer 리셋
                            human_move_timer = self.human_move_time_limit

                            # 게임 종료 체크
                            if self.board.is_game_over():
                                outcome = self.board.outcome()
                                winner = None
                                if outcome.winner is True:
                                    winner = "white"
                                elif outcome.winner is False:
                                    winner = "black"
                                return {
                                    "game_over": True,
                                    "result": "checkmate_or_draw",
                                    "winner": winner,
                                    "board": self.board,
                                }
                        else:
                            # 불법수 → 선택 해제
                            self.selected_square = None

            # AI 턴 처리
            if (not self.is_human_turn()) and (not self.board.is_game_over()):
                self.make_ai_move()
                ai_move_timer = self.ai_move_time_limit

                if self.board.is_game_over():
                    outcome = self.board.outcome()
                    winner = None
                    if outcome.winner is True:
                        winner = "white"
                    elif outcome.winner is False:
                        winner = "black"
                    return {
                        "game_over": True,
                        "result": "checkmate_or_draw",
                        "winner": winner,
                        "board": self.board,
                    }

            # 그리기
            self.screen.fill(self.BLACK)
            self.draw_board()
            self.draw_hud(round_timer, human_move_timer, ai_move_timer)
            pygame.display.flip()
