# game_manager.py
import random
from ChessGame import ChessGUI
from box_GAME import BoxingGUI  # 네가 구현해둔 복싱 GUI


class ChessBoxingManager:
    """
    체스-복싱-체스-복싱 ... 번갈아가며 진행하는 매니저.

    - 체스: ChessGUI 사용
    - 복싱: BoxingGUI 사용 (라운드 타이머 없음, 죽으면 끝)
    - 복싱 결과에 따라 다음 체스 라운드에 디버프 부여
    """

    def __init__(
        self,
        chess_round_time: float = 40.0,  # 체스 한 라운드 전체 시간
        chess_move_time: float = 5.0,    # 한 수당 제한 시간
    ):
        # 체스 설정
        self.chess_round_time = chess_round_time
        self.chess_move_time = chess_move_time

        # 현재 체스 포지션 (None이면 새 게임)
        self.current_board = None

        # 다음 체스 라운드에 적용할 디버프 (dict)
        self.next_chess_debuff = {}

        # 전체 게임 종료 여부
        self.game_over = False
        self.final_winner = None  # "white" or "black" or None(무승부)

    # ------------------------------
    # 디버프 생성 로직
    # ------------------------------
    def compute_debuff_from_boxing(self, boxing_result: dict) -> dict:
        """
        복싱 결과(bres)를 받아서 다음 체스 라운드에 적용할 디버프 dict를 만든다.
        - P1 = 사람(white), P2 = AI(black) 라고 가정
        - 복싱에서 P1이 패배하면: 사람에게 불리한 디버프 부여
        - P2가 패배하거나 무승부면: 디버프 없음 (필요하면 반대로도 줄 수 있음)
        """
        winner = boxing_result.get("winner", None)
        p1_hp = boxing_result.get("p1_hp", 0)
        p2_hp = boxing_result.get("p2_hp", 0)

        # 사람(P1)이 지지 않으면 디버프 없음
        if winner != "P2":
            return {}

        # HP 차이로 얼마나 크게 졌는지 판단
        hp_diff = max(0, p2_hp - p1_hp)

        debuffs = []

        # 1) 수당 시간 감소 디버프
        if hp_diff >= 2:
            debuffs.append({"move_time_factor": 0.5})  # 50%
        else:
            debuffs.append({"move_time_factor": 0.7})  # 70%

        # 2) 시야 가리기 (왼쪽/오른쪽 말 안 보이게)
        debuffs.append({"blind_side": random.choice(["left", "right"])})

        # 3) 상대 말 ? 처리
        debuffs.append({"hide_enemy_pieces": True})

        # 위 디버프 중 1~2개만 랜덤 적용
        k = random.randint(1, 2)
        chosen = random.sample(debuffs, k=k)

        merged = {}
        for d in chosen:
            merged.update(d)
        return merged

    # ------------------------------
    # 라운드 실행 함수들
    # ------------------------------
    def run_chess_round(self):
        """
        체스 라운드를 한 번 실행하고 결과(dict)를 반환.
        - self.current_board / self.next_chess_debuff 를 사용/업데이트한다.
        """
        gui = ChessGUI(
            round_time=self.chess_round_time,
            move_time=self.chess_move_time,
            debuff=self.next_chess_debuff,
            board=self.current_board,
        )
        result = gui.run()

        # 체스 포지션 저장 (항상 유지)
        self.current_board = result["board"]

        # 체스 게임이 완전히 끝났다면 전체 매치 종료
        if result["game_over"]:
            self.game_over = True
            self.final_winner = result.get("winner", None)  # "white" or "black" or None

        return result

    def run_boxing_round(self):
        """
        복싱 라운드를 한 번 실행하고 결과(dict)를 반환.
        -> BoxingGUI는 라운드 타이머 없이, 누군가 쓰러질 때까지 진행된다고 가정.
        """
        gui = BoxingGUI()
        result = gui.run()
        # result 예시:
        # {
        #   "winner": "P1" or "P2" or None,
        #   "p1_hp": int,
        #   "p2_hp": int,
        # }
        return result

    # ------------------------------
    # 메인 루프
    # ------------------------------
    def main_loop(self):
        """
        체스 -> 복싱 -> 체스 -> 복싱 ... 반복.
        체스 게임(체크메이트/무승부/타임아웃)이 끝나면 전체 종료.
        """
        round_index = 1
        self.next_chess_debuff = {}  # 첫 체스 라운드는 디버프 없음

        while not self.game_over:
            print(f"=== 체스 라운드 {round_index} 시작 ===")
            chess_res = self.run_chess_round()
            print("체스 라운드 결과:", chess_res["result"], "winner:", chess_res["winner"])

            if self.game_over:
                print("체스 게임 종료! 최종 승자:", self.final_winner)
                break

            print(f"=== 복싱 라운드 {round_index} 시작 ===")
            boxing_res = self.run_boxing_round()
            print(
                "복싱 라운드 결과: winner:", boxing_res.get("winner"),
                "HP => P1:", boxing_res.get("p1_hp"), "P2:", boxing_res.get("p2_hp")
            )

            # 복싱 결과 기반으로 다음 체스 라운드 디버프 계산
            self.next_chess_debuff = self.compute_debuff_from_boxing(boxing_res)
            print("다음 체스 라운드 디버프:", self.next_chess_debuff)

            round_index += 1


if __name__ == "__main__":
    manager = ChessBoxingManager(
        chess_round_time=40.0,  # 한 체스 라운드 최대 40초
        chess_move_time=5.0,    # 한 수당 5초
    )
    manager.main_loop()
