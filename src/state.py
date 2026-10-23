"""Game state containers shared by the rules engine."""

STARTING_CASH = 1500
JAIL_POS = 10
GO_TO_JAIL_POS = 30
PASS_GO_BONUS = 200
JAIL_FINE = 50

PLAYER_COLORS = ["#e63946", "#1d3557", "#2a9d8f", "#e76f51"]
TOKENS = [("Top Hat", "\U0001F3A9"), ("Dog", "\U0001F415"),
          ("Car", "\U0001F697"), ("Boot", "\U0001F97E")]


class Player:
    __slots__ = ("pid", "name", "glyph", "color", "cash", "pos", "in_jail",
                 "jail_rolls", "goojf", "bankrupt")

    def __init__(self, pid):
        self.pid = pid
        self.name = f"Player {pid + 1}"
        self.glyph = TOKENS[pid][1]
        self.color = PLAYER_COLORS[pid]
        self.cash = STARTING_CASH
        self.pos = 0
        self.in_jail = False
        self.jail_rolls = 0
        self.goojf = []                   # deck names of held GOOJF cards
        self.bankrupt = False

    def to_dict(self):
        return {"pid": self.pid, "name": self.name, "glyph": self.glyph,
                "color": self.color, "cash": self.cash, "pos": self.pos,
                "in_jail": self.in_jail, "jail_rolls": self.jail_rolls,
                "goojf": len(self.goojf), "bankrupt": self.bankrupt}


class GameState:
    def __init__(self, n_players=4):
        self.players = [Player(i) for i in range(n_players)]
        self.owner = [None] * 40          # square idx -> player id or None
        self.houses = [0] * 40            # 0..4 houses, 5 = hotel
        self.mortgaged = [False] * 40
        self.chance_deck = []             # card ids, top at index 0
        self.chest_deck = []
        self.current = 0
        self.turn = 1
        self.doubles = 0                  # consecutive doubles this turn
        self.last_dice = None
        self.phase = "await_roll"
        self.pending = None
        self.winner = None
        self.log = []
        self.anim = None

    def to_dict(self, squares):
        return {
            "squares": squares,
            "players": [p.to_dict() for p in self.players],
            "owner": self.owner,
            "houses": self.houses,
            "mortgaged": self.mortgaged,
            "current": self.current,
            "turn": self.turn,
            "doubles": self.doubles,
            "dice": self.last_dice,
            "phase": self.phase,
            "pending": self.pending,
            "winner": self.winner,
            "log": self.log,
        }
