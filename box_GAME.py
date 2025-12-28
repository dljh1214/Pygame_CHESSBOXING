# boxing_gui.py
import pygame
import random
from pygame.locals import *
from box2 import BoxingGame


class BoxingGUI:
    WIDTH = 900
    HEIGHT = 600
    TILE_SIZE = 60
    MIN_X = -5
    MAX_X = 5

    def __init__(self):
        # pygame 관련 필드
        self.screen = None
        self.clock = None
        self.font = None

        # 게임 로직
        self.game = BoxingGame()
        self.game.setup()

        # 좌표계
        self.center_x = self.WIDTH // 2
        self.y_line = self.HEIGHT // 2

        # UI 상태
        self.selected_card = None  # (from_list, index, card_obj)
        self.selected_dir = None   # -1 or 1
        self.last_message = "게임 시작!"

        self.last_p1_dir = None
        self.last_p2_dir = None
        self.last_p1_target_x = None
        self.last_p2_target_x = None

    # ---------------------------
    # 좌표/유틸 함수
    # ---------------------------
    def x_to_pixel(self, x: int) -> int:
        """1D 필드 좌표 -> 화면 픽셀 x(타일 중앙 기준)"""
        return self.center_x + x * self.TILE_SIZE

    def compute_target_x(self, player, card, direction):
        """
        이 카드가 이번 턴에 '어느 칸'을 노리는지 계산해서 x좌표(int)를 돌려준다.
        - 이동 카드: distance 사용
        - 공격/유틸 카드: range 사용
        - 아무 공간효과 없으면 None
        """
        dist = getattr(card, "distance", 0)
        if dist:
            return player.x + direction * dist

        rng = getattr(card, "range", 0)
        if rng:
            return player.x + direction * rng

        return None

    # ---------------------------
    # 그리기 관련
    # ---------------------------
    def draw_target_tile(self, target_x, color):
        """타겟 칸(x)을 하이라이트"""
        if target_x is None:
            return
        if target_x < self.MIN_X or target_x > self.MAX_X:
            return

        tile_center_x = self.x_to_pixel(target_x)
        tile_w = self.TILE_SIZE
        tile_h = 50

        rect = pygame.Rect(
            tile_center_x - tile_w // 2,
            self.y_line - tile_h // 2,
            tile_w,
            tile_h,
        )
        pygame.draw.rect(self.screen, color, rect, 3)

    def draw_direction_arrow(self, x, y, direction, color):
        if direction is None:
            return
        size = 12

        if direction == -1:  # 왼쪽
            points = [
                (x - size, y),
                (x, y - size),
                (x, y + size),
            ]
        else:  # 오른쪽
            points = [
                (x + size, y),
                (x, y - size),
                (x, y + size),
            ]
        pygame.draw.polygon(self.screen, color, points)

    def draw_status(self, player, x, y):
        s = []
        if player.cc.stunned:
            s.append("STUN")
        if player.cc.guarded:
            s.append("G")
        if player.cc.fixed:
            s.append("FIX")
        if player.cc.combi_buff:
            s.append("CMB")
        if player.cc.counter_on:
            s.append("CTR")
        if s:
            txt = self.font.render(",".join(s), True, (255, 255, 0))
            self.screen.blit(txt, (x - 30, y))

    def draw_scene(self):
        game = self.game
        screen = self.screen
        font = self.font

        screen.fill((30, 30, 30))

        # 타일 바닥
        for tx in range(self.MIN_X, self.MAX_X + 1):
            cx = self.x_to_pixel(tx)
            rect = pygame.Rect(
                cx - self.TILE_SIZE // 2,
                self.y_line - self.TILE_SIZE // 2,
                self.TILE_SIZE,
                self.TILE_SIZE,
            )
            pygame.draw.rect(screen, (60, 60, 60), rect)
            pygame.draw.rect(screen, (120, 120, 120), rect, 2)

            num_txt = font.render(str(tx), True, (180, 180, 180))
            screen.blit(
                num_txt,
                (rect.x + self.TILE_SIZE // 2 - 8, rect.y + self.TILE_SIZE // 2 - 10),
            )

        # 플레이어 위치
        p1_x = self.x_to_pixel(game.p1.x)
        p1_y = self.y_line
        pygame.draw.circle(screen, (0, 200, 255), (p1_x, p1_y), 20)

        p2_x = self.x_to_pixel(game.p2.x)
        p2_y = self.y_line
        pygame.draw.circle(screen, (255, 100, 100), (p2_x, p2_y), 20)

        # 방향 화살표
        self.draw_direction_arrow(p1_x, p1_y, self.last_p1_dir, (0, 255, 255))
        self.draw_direction_arrow(p2_x, p2_y, self.last_p2_dir, (255, 150, 150))

        # 타겟 타일
        self.draw_target_tile(self.last_p1_target_x, (0, 255, 0))
        self.draw_target_tile(self.last_p2_target_x, (255, 80, 80))

        # HP 표시
        hp_text1 = font.render(f"P1 HP: {game.p1.hp}", True, (255, 255, 255))
        hp_text2 = font.render(f"P2 HP: {game.p2.hp}", True, (255, 255, 255))
        screen.blit(hp_text1, (50, 20))
        screen.blit(hp_text2, (self.WIDTH - 200, 20))

        # 상태표시
        self.draw_status(game.p1, p1_x, self.y_line + 40)
        self.draw_status(game.p2, p2_x, self.y_line - 40)

        # 카드 버튼
        x_start = 50
        y_basic = self.HEIGHT - 200
        y_special = self.HEIGHT - 160
        btn_w, btn_h = 120, 30

        # 기본 카드
        for i, card in enumerate(game.p1.basic_cards):
            rect = pygame.Rect(x_start + i * (btn_w + 10), y_basic, btn_w, btn_h)
            is_move = getattr(card, "type", None) == BoxingGame.Type.Move
            if game.p1.cc.fixed and is_move:
                color = (40, 40, 40)
                text_color = (120, 120, 120)
            else:
                color = (60, 60, 60)
                text_color = (255, 255, 255)
            pygame.draw.rect(screen, color, rect)
            txt = font.render(card.__class__.__name__, True, text_color)
            screen.blit(txt, (rect.x + 5, rect.y + 5))

        # 스페셜 카드
        for i, card in enumerate(game.p1.special_cards):
            rect = pygame.Rect(x_start + i * (btn_w + 10), y_special, btn_w, btn_h)
            is_move = getattr(card, "type", None) == BoxingGame.Type.Move
            if game.p1.cc.fixed and is_move:
                color = (50, 40, 50)
                text_color = (150, 150, 150)
            else:
                color = (80, 60, 80)
                text_color = (255, 255, 255)
            pygame.draw.rect(screen, color, rect)
            txt = font.render(card.__class__.__name__, True, text_color)
            screen.blit(txt, (rect.x + 5, rect.y + 5))

        # 방향 버튼
        left_rect = pygame.Rect(50, self.HEIGHT - 80, 50, 30)
        right_rect = pygame.Rect(150, self.HEIGHT - 80, 50, 30)
        pygame.draw.rect(screen, (80, 80, 80), left_rect)
        pygame.draw.rect(screen, (80, 80, 80), right_rect)
        ltxt = font.render("<", True, (255, 255, 255))
        rtxt = font.render(">", True, (255, 255, 255))
        screen.blit(ltxt, (left_rect.x + 15, left_rect.y + 5))
        screen.blit(rtxt, (right_rect.x + 15, right_rect.y + 5))

        # 선택 상태
        sel_card_name = self.selected_card[2].__class__.__name__ if self.selected_card else "-"
        sel_dir_str = {None: "-", -1: "왼쪽", 1: "오른쪽"}[self.selected_dir]
        info_text = font.render(
            f"선택 카드: {sel_card_name} / 방향: {sel_dir_str}",
            True,
            (255, 255, 255),
        )
        screen.blit(info_text, (50, self.HEIGHT - 120))

        msg_text = font.render(self.last_message, True, (200, 200, 0))
        screen.blit(msg_text, (50, self.HEIGHT - 30))

        # 게임 종료 메시지
        if self.game.game_over:
            winner = (
                "P2 승!" if self.game.p1.hp <= 0 and self.game.p2.hp > 0
                else "P1 승!" if self.game.p2.hp <= 0 and self.game.p1.hp > 0
                else "무승부"
            )
            over_text = font.render(f"게임 종료: {winner}", True, (255, 50, 50))
            self.screen.blit(
                over_text,
                (self.WIDTH // 2 - 100, self.HEIGHT // 2 - 100),
            )

    # ---------------------------
    # 이벤트 처리
    # ---------------------------
    def handle_mouse_click(self, pos):
        if self.game.game_over:
            return

        mx, my = pos
        game = self.game

        # 방향 버튼
        if 50 <= mx <= 100 and self.HEIGHT - 80 <= my <= self.HEIGHT - 50:
            self.selected_dir = -1
            self.last_message = "방향: 왼쪽"
            return

        if 150 <= mx <= 200 and self.HEIGHT - 80 <= my <= self.HEIGHT - 50:
            self.selected_dir = 1
            self.last_message = "방향: 오른쪽"
            return

        # 카드 버튼
        card_btns = []
        x_start = 50
        y_basic = self.HEIGHT - 200
        y_special = self.HEIGHT - 160
        btn_w, btn_h = 120, 30

        # 기본 카드
        for i, card in enumerate(game.p1.basic_cards):
            rect = pygame.Rect(x_start + i * (btn_w + 10), y_basic, btn_w, btn_h)
            card_btns.append(("basic", i, rect, card))

        # 스페셜 카드
        for i, card in enumerate(game.p1.special_cards):
            rect = pygame.Rect(x_start + i * (btn_w + 10), y_special, btn_w, btn_h)
            card_btns.append(("special", i, rect, card))

        for from_list, idx, rect, card in card_btns:
            if rect.collidepoint(mx, my):
                # fixed 상태면 이동카드 사용 불가
                if game.p1.cc.fixed and getattr(card, "type", None) == BoxingGame.Type.Move:
                    self.last_message = "이동 불가 상태입니다! (fixed)"
                    return
                self.selected_card = (from_list, idx, card)
                self.last_message = f"카드 선택: {card.__class__.__name__}"
                return

    # ---------------------------
    # 턴 처리
    # ---------------------------
    def process_turn_if_ready(self):
        game = self.game
        if self.selected_card is None or self.selected_dir is None:
            return
        if game.game_over:
            return

        from_list, idx, card = self.selected_card

        # P1 액션
        act1 = BoxingGame.Action(game.p1, card, self.selected_dir)

        # 카드 소모
        if from_list == "basic":
            if 0 <= idx < len(game.p1.basic_cards) and game.p1.basic_cards[idx] is card:
                game.p1.basic_cards.pop(idx)
        elif from_list == "special":
            if 0 <= idx < len(game.p1.special_cards) and game.p1.special_cards[idx] is card:
                game.p1.special_cards.pop(idx)

        # P2 (AI)
        ai_cards = game.p2.basic_cards + game.p2.special_cards
        if ai_cards:
            ai_card = random.choice(ai_cards)
            if game.p1.x < game.p2.x:
                ai_dir = -1
            elif game.p1.x > game.p2.x:
                ai_dir = 1
            else:
                ai_dir = random.choice([-1, 1])
            act2 = BoxingGame.Action(game.p2, ai_card, ai_dir)

            # AI 카드 소모
            if ai_card in game.p2.basic_cards:
                game.p2.basic_cards.remove(ai_card)
            elif ai_card in game.p2.special_cards:
                game.p2.special_cards.remove(ai_card)
        else:
            ai_card = BoxingGame.Jab()
            ai_dir = random.choice([-1, 1])
            act2 = BoxingGame.Action(game.p2, ai_card, ai_dir)

        # 방향/타겟 기록 (시각화용)
        self.last_p1_dir = act1.direction
        self.last_p2_dir = act2.direction
        self.last_p1_target_x = self.compute_target_x(game.p1, card, act1.direction)
        self.last_p2_target_x = self.compute_target_x(game.p2, ai_card, act2.direction)

        # 턴 해소
        game.resolve_turn(act1, act2)
        self.last_message = (
            f"턴 {game.turn} 진행! P1:{card.__class__.__name__} / "
            f"P2:{ai_card.__class__.__name__}"
        )

        # 선택 초기화
        self.selected_card = None
        self.selected_dir = None

    # ---------------------------
    # 메인 루프
    # ---------------------------
    def run(self):
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.setCaption = "BoxingGame - Pygame Prototype"
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("malgungothic", 20)

        running = True
        while running:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_mouse_click(event.pos)

            # 턴 처리
            self.process_turn_if_ready()

            # 화면 그리기
            self.draw_scene()
            pygame.display.flip()

        pygame.quit()
        # 상위에서 참고할 수 있도록 결과 리턴
        return {
            "game_over": self.game.game_over,
            "winner": getattr(self.game, "winner", None),
            "p1_hp": self.game.p1.hp,
            "p2_hp": self.game.p2.hp,
        }


if __name__ == "__main__":
    gui = BoxingGUI()
    gui.run()
