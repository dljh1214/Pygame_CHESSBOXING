from enum import Enum
import random
import heapq


class BoxingGame:
    PLAYER_BASIC_HEALTH = 3
    NOW_GAME = None        # 전역에서 현재 게임 인스턴스 참조
    _cc_order = 0          # 상태 스케줄용 전역 우선순위 카운터

    FIELD_MIN_X = -5
    FIELD_MAX_X = 5
    SPECIAL_CARD_NUM = 5

    @staticmethod
    def clamp_pos(player):
        """플레이어 x 위치를 -5 ~ 5 사이로 고정"""
        if player.x < BoxingGame.FIELD_MIN_X:
            player.x = BoxingGame.FIELD_MIN_X
        elif player.x > BoxingGame.FIELD_MAX_X:
            player.x = BoxingGame.FIELD_MAX_X
    # -------------------------
    #   ENUM & 컨트롤러
    # -------------------------
    class Type(Enum):
        Move = 1
        Util = 2
        Attack = 3

    class ControlM:
        """상태이상/버프 관리 클래스"""
        def __init__(self):
            self.guarded = False
            self.stunned = False
            self.fixed = False
            self.combi_buff = False
            self.counter_on = None  # Counter 카드 인스턴스 or None
            self._queue = []        # (turn, order, fn)

        def schedule(self, turn, fn):
            """turn 턴 시작 시점에 fn을 실행한다."""
            BoxingGame._cc_order += 1
            heapq.heappush(self._queue, (turn, BoxingGame._cc_order, fn))

        def update(self, current_turn):
            """해당 턴 시작 시점에 실행할 상태 이벤트 처리"""
            while self._queue and self._queue[0][0] <= current_turn:
                _, _, fn = heapq.heappop(self._queue)
                fn()

    # -------------------------
    #       액션 컨텍스트
    # -------------------------
    class ActionContext:
        def __init__(self, game, player, target, direction, damage_map):
            self.game = game
            self.player = player
            self.target = target
            self.direction = direction  # -1 or 1
            self.damage = damage_map    # dict: {player: int}

    # -------------------------
    #         카드 베이스
    # -------------------------
    class Card:
        def __init__(self, card_type, name=None):
            self.type = card_type
            self.name = name or self.__class__.__name__

        def act(self, ctx: "BoxingGame.ActionContext"):
            """
            공통 처리:
            - 스턴이면 아무것도 안 함
            - 공격 카드라면 먼저 '상대 카운터' 체크
            - Combi 버프 추가타 처리 (공격판정 X, 가드/카운터 무시)
            - 그 이후 실제 효과(resolve)
            """
            p = ctx.player
            t = ctx.target
            d = ctx.direction

            # 1. 스턴이면 행동 불가
            if p.cc.stunned:
                return

            # 2. 공격 카드 + 상대가 Counter 켜둔 상태면 → 즉시 카운터 발동
            if (
                    self.type == BoxingGame.Type.Attack
                    and isinstance(t.cc.counter_on, BoxingGame.Counter)
            ):
                # 내 공격은 전부 씹히고, Counter 쪽에서 반격/스턴 처리
                t.cc.counter_on.on_countered_attack(attacker=p, ctx=ctx)
                return

            # 3. Combi 버프 추가타 (이건 공격 판정 아니라서 카운터에 안 막힘)
            if p.cc.combi_buff:
                if p.x + d == t.x:
                    ctx.damage[t] += 1

            # 4. 실제 카드 효과
            self.resolve(ctx)

        def resolve(self, ctx: "BoxingGame.ActionContext"):
            """각 카드에서 오버라이드해서 사용"""
            pass

        # 공격 카드에서 쓸 공통 로직
        def apply_attack(self, ctx, range_, damage, ignore_guard=False, ignore_counter=False):
            p = ctx.player
            t = ctx.target
            d = ctx.direction

            # 사거리 체크
            if p.x + d * range_ != t.x:
                return

            # 카운터 체크
            if (not ignore_counter) and isinstance(t.cc.counter_on, BoxingGame.Counter):
                t.cc.counter_on.on_countered_attack(attacker=p, ctx=ctx)
                return

            # 가드 체크
            if (not ignore_guard) and t.cc.guarded:
                return

            # 데미지 기록 (실제 HP 감소는 턴 끝에서 한 번에)
            ctx.damage[t] += damage

    # -------------------------
    #     기본 카드들
    # -------------------------
    class Jab(Card):        # 데미지 1, 사거리 1
        def __init__(self):
            super().__init__(BoxingGame.Type.Attack)

        def resolve(self, ctx):
            self.apply_attack(ctx, range_=1, damage=1)

    class Step(Card):       # 거리 1 이동
        def __init__(self):
            super().__init__(BoxingGame.Type.Move)

        def resolve(self, ctx):
            p = ctx.player
            d = ctx.direction
            if not p.cc.fixed:
                p.x += d * 1
                BoxingGame.clamp_pos(p)

    class Guard(Card):      # 이번 턴동안 공격 스킬 무시
        def __init__(self):
            super().__init__(BoxingGame.Type.Util)
            self._owner = None

        def resolve(self, ctx):
            game = ctx.game
            p = ctx.player
            self._owner = p
            p.cc.guarded = True

            # 다음 턴 시작 시 가드 해제
            def clear_guard():
                self._owner.cc.guarded = False

            p.cc.schedule(game.turn + 1, clear_guard)

    # -------------------------
    #     스페셜 카드들
    # -------------------------
    class Straight(Card):  # 데미지 2, 사거리 1
        def __init__(self):
            super().__init__(BoxingGame.Type.Attack)

        def resolve(self, ctx):
            self.apply_attack(ctx, range_=1, damage=2)

    class Counter(Card):   # 카운터
        def __init__(self):
            super().__init__(BoxingGame.Type.Util)
            self.owner = None
            self.triggered = False  # 한 번만 발동

        def resolve(self, ctx):
            p = ctx.player
            self.owner = p
            p.cc.counter_on = self  # 이번 턴 동안 카운터 대기

        def on_countered_attack(self, attacker, ctx):
            """카운터가 공격을 받아쳤을 때"""
            if self.triggered:
                return
            self.triggered = True

            game = ctx.game

            # 반격 데미지 1
            ctx.damage[attacker] += 1

            # 공격자: 다음 턴 행동 불가 (stun), 그 다음 턴에 해제
            def set_stun():
                attacker.cc.stunned = True

            def clear_stun():
                attacker.cc.stunned = False

            attacker.cc.schedule(game.turn + 1, set_stun)
            attacker.cc.schedule(game.turn + 2, clear_stun)

            # 카운터 종료
            if self.owner.cc.counter_on is self:
                self.owner.cc.counter_on = None

        def fail(self):
            """그 턴 동안 공격을 받아치지 못하고 끝난 경우"""
            if self.triggered:
                return
            owner = self.owner
            game = BoxingGame.NOW_GAME
            if owner is None or game is None:
                return

            # 자신 다음 턴 stun, 그 다음 턴에 해제
            def set_stun():
                owner.cc.stunned = True

            def clear_stun():
                owner.cc.stunned = False

            owner.cc.schedule(game.turn + 1, set_stun)
            owner.cc.schedule(game.turn + 2, clear_stun)

            # 카운터 종료
            if owner.cc.counter_on is self:
                owner.cc.counter_on = None

    class Hook(Card):     # 가드/카운터 무시, 데미지 1, 사거리 1
        def __init__(self):
            super().__init__(BoxingGame.Type.Attack)

        def resolve(self, ctx):
            # guard/counter 무시
            self.apply_attack(ctx, range_=1, damage=1, ignore_guard=True, ignore_counter=True)

    class Pound(Card):    # 데미지 없음, 사거리 1, 적중 시 상대 다음 턴 이동 스킬 사용 불가
        def __init__(self):
            super().__init__(BoxingGame.Type.Util)

        def resolve(self, ctx):
            game = ctx.game
            p = ctx.player
            t = ctx.target
            d = ctx.direction

            if p.x + d * 1 != t.x:
                return

            # 다음 턴 고정 상태 fixed=True, 다다음 턴에 해제
            def set_fixed():
                t.cc.fixed = True

            def clear_fixed():
                t.cc.fixed = False

            t.cc.schedule(game.turn + 1, set_fixed)
            t.cc.schedule(game.turn + 2, clear_fixed)

    class Footwork(Card): # 한번에 2칸 이동
        def __init__(self):
            super().__init__(BoxingGame.Type.Move)

        def resolve(self, ctx):
            p = ctx.player
            d = ctx.direction
            if not p.cc.fixed:
                p.x += d * 2
                BoxingGame.clamp_pos(p)

    class Combi(Card):   # 앞으로 한칸 이동, 다음 턴에 사거리1 추가 공격 버프(공격 판정 X)
        def __init__(self):
            super().__init__(BoxingGame.Type.Move)
            self.owner = None

        def resolve(self, ctx):
            game = ctx.game
            p = ctx.player
            d = ctx.direction
            self.owner = p

            # 다음 턴에 combi_buff ON, 다다음 턴에 OFF
            def enable_buff():
                p.cc.combi_buff = True

            def disable_buff():
                p.cc.combi_buff = False

            p.cc.schedule(game.turn + 1, enable_buff)
            p.cc.schedule(game.turn + 2, disable_buff)

            # 이동 파트 (fixed면 이동 불가)
            if not p.cc.fixed:
                p.x += d * 1
                BoxingGame.clamp_pos(p)

    class Uppercut(Card): # 사거리 0, 데미지 1
        def __init__(self):
            super().__init__(BoxingGame.Type.Attack)

        def resolve(self, ctx):
            self.apply_attack(ctx, range_=0, damage=1)

    class Kick(Card):    # 사거리 2, 데미지 1
        def __init__(self):
            super().__init__(BoxingGame.Type.Attack)

        def resolve(self, ctx):
            self.apply_attack(ctx, range_=2, damage=1)

    # 스페셜 카드 풀
    SPECIAL_CARD_LIST = [Straight, Counter, Hook, Pound, Footwork, Combi, Uppercut, Kick]

    # -------------------------
    #       AI & 액션
    # -------------------------
    class AI:
        pass  # 지금은 랜덤 선택만 Pygame 쪽에서 처리

    class Action:
        def __init__(self, player, card, direction):
            self.player = player
            self.card = card
            self.direction = direction   # -1 or 1
            # 대상은 "나 아닌 다른 플레이어"
            self.target = BoxingGame.NOW_GAME.p1 if player == BoxingGame.NOW_GAME.p2 else BoxingGame.NOW_GAME.p2

    # -------------------------
    #         플레이어
    # -------------------------
    class Player:
        PLAYER_LOC = (-1, 1)
        PLAYER_NUM = 0

        def __init__(self, control=None):
            self.basic_cards = []
            self.special_cards = []
            self.ai = control
            self.hp = BoxingGame.PLAYER_BASIC_HEALTH
            self.num = BoxingGame.Player.PLAYER_NUM
            self.x = BoxingGame.Player.PLAYER_LOC[self.num]
            BoxingGame.Player.PLAYER_NUM += 1
            self.cc = BoxingGame.ControlM()

        def setup(self):
            self.x = BoxingGame.Player.PLAYER_LOC[self.num]
            self.basic_cards = [
                BoxingGame.Jab(),
                BoxingGame.Step(),
                BoxingGame.Guard()
            ]
            # 랜덤 2장 스페셜
            self.special_cards = [cls() for cls in random.sample(BoxingGame.SPECIAL_CARD_LIST, BoxingGame.SPECIAL_CARD_NUM)]

        def refill(self):
            """기본 카드가 다 쓰이면 다시 3장 세트로 리필"""
            if not self.basic_cards:
                self.basic_cards = [
                    BoxingGame.Jab(),
                    BoxingGame.Step(),
                    BoxingGame.Guard()
                ]

    # -------------------------
    #          게임 본체
    # -------------------------
    def __init__(self):
        self.p1 = BoxingGame.Player()
        self.p2 = BoxingGame.Player(BoxingGame.AI())
        self.turn = 0
        self.game_over = False
        self.winner = None  # 'P1', 'P2', None(무승부)
        BoxingGame.NOW_GAME = self

    def setup(self):
        self.p1.setup()
        self.p2.setup()

    def resolve_turn(self, act1: "BoxingGame.Action", act2: "BoxingGame.Action"):
        if self.game_over:
            return

        # 턴 증가
        self.turn += 1

        # 턴 시작: 상태 업데이트 + 기본카드 리필
        for pl in [self.p1, self.p2]:
            pl.cc.update(self.turn)
            pl.refill()

        # 공격 데미지 동시 적용을 위해 누적
        damage = {self.p1: 0, self.p2: 0}

        # 액션 우선순위 정렬 (Move → Util → Attack)
        actions = [act1, act2]
        actions.sort(key=lambda a: a.card.type.value)

        # 각 액션 수행 (데미지는 damage dict에만 누적)
        for action in actions:
            ctx = BoxingGame.ActionContext(
                game=self,
                player=action.player,
                target=action.target,
                direction=action.direction,
                damage_map=damage
            )
            action.card.act(ctx)

        # 카운터 실패 처리 (이 턴 동안 한 번도 트리거 안 된 경우)
        for pl in [self.p1, self.p2]:
            c = pl.cc.counter_on
            if isinstance(c, BoxingGame.Counter) and not c.triggered:
                c.fail()

        # 누적된 데미지를 동시에 적용
        self.p1.hp -= damage[self.p1]
        self.p2.hp -= damage[self.p2]

        # 승패 판정
        if self.p1.hp <= 0 and self.p2.hp <= 0:
            self.game_over = True
            self.winner = None  # 무승부
        elif self.p1.hp <= 0:
            self.game_over = True
            self.winner = "P2"
        elif self.p2.hp <= 0:
            self.game_over = True
            self.winner = "P1"
