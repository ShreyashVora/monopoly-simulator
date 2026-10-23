"""Standard US Monopoly board data (40 squares) with full rent tables."""

GROUPS = {
    "brown": ["Mediterranean Avenue", "Baltic Avenue"],
    "lightblue": ["Oriental Avenue", "Vermont Avenue", "Connecticut Avenue"],
    "pink": ["St. Charles Place", "States Avenue", "Virginia Avenue"],
    "orange": ["St. James Place", "Tennessee Avenue", "New York Avenue"],
    "red": ["Kentucky Avenue", "Indiana Avenue", "Illinois Avenue"],
    "yellow": ["Atlantic Avenue", "Ventnor Avenue", "Marvin Gardens"],
    "green": ["Pacific Avenue", "North Carolina Avenue", "Pennsylvania Avenue"],
    "darkblue": ["Park Place", "Boardwalk"],
}

COLORS = {
    "brown": "#955436", "lightblue": "#AAE0FA", "pink": "#D93A96",
    "orange": "#F7941D", "red": "#ED1B24", "yellow": "#FEF200",
    "green": "#1FB25A", "darkblue": "#0072BB",
    "railroad": "#2B2B2B", "utility": "#CFCFCF",
}


def _street(short, name, group, price, rents, house_cost):
    return {"idx": None, "short": short, "name": name, "type": "street",
            "group": group, "price": price, "rents": list(rents),
            "house_cost": house_cost, "mortgage": price // 2}


def _railroad(name, price=200):
    return {"idx": None, "short": name, "name": name, "type": "railroad",
            "group": "railroad", "price": price, "rents": [25, 50, 100, 200],
            "house_cost": None, "mortgage": price // 2}


def _utility(name, price=150):
    return {"idx": None, "short": name, "name": name, "type": "utility",
            "group": "utility", "price": price, "rents": None,
            "house_cost": None, "mortgage": price // 2}


def _special(short, name, kind, amount=None):
    return {"idx": None, "short": short, "name": name, "type": kind,
            "group": None, "price": None, "rents": None,
            "house_cost": None, "mortgage": None, "amount": amount}


def _squares():
    return [
        _special("GO", "GO", "go"),                                        # 0
        _street("Mediterranean Ave", "Mediterranean Avenue", "brown",
                60, (2, 10, 30, 90, 160, 250), 50),
        _special("Community Chest", "Community Chest 1", "chest"),         # 2
        _street("Baltic Ave", "Baltic Avenue", "brown",
                60, (4, 20, 60, 180, 320, 450), 50),
        _special("Income Tax", "Income Tax", "tax", 200),                  # 4
        _railroad("Reading Railroad"),                                     # 5
        _street("Oriental Ave", "Oriental Avenue", "lightblue",
                100, (6, 30, 90, 270, 400, 550), 50),
        _special("Chance", "Chance 1", "chance"),                          # 7
        _street("Vermont Ave", "Vermont Avenue", "lightblue",
                100, (6, 30, 90, 270, 400, 550), 50),
        _street("Connecticut Ave", "Connecticut Avenue", "lightblue",
                120, (8, 40, 100, 300, 450, 600), 50),
        _special("Jail", "Jail / Just Visiting", "jail"),                  # 10
        _street("St. Charles Place", "St. Charles Place", "pink",
                140, (10, 50, 150, 450, 625, 750), 100),
        _utility("Electric Company"),                                      # 12
        _street("States Ave", "States Avenue", "pink",
                140, (10, 50, 150, 450, 625, 750), 100),
        _street("Virginia Ave", "Virginia Avenue", "pink",
                160, (12, 60, 180, 500, 700, 900), 100),
        _railroad("Pennsylvania Railroad"),                                # 15
        _street("St. James Place", "St. James Place", "orange",
                180, (14, 70, 200, 550, 750, 950), 100),
        _special("Community Chest", "Community Chest 2", "chest"),         # 17
        _street("Tennessee Ave", "Tennessee Avenue", "orange",
                180, (14, 70, 200, 550, 750, 950), 100),
        _street("New York Ave", "New York Avenue", "orange",
                200, (16, 80, 220, 600, 800, 1000), 100),
        _special("Free Parking", "Free Parking", "free_parking"),          # 20
        _street("Kentucky Ave", "Kentucky Avenue", "red",
                220, (18, 90, 250, 700, 875, 1050), 150),
        _special("Chance", "Chance 2", "chance"),                          # 22
        _street("Indiana Ave", "Indiana Avenue", "red",
                220, (18, 90, 250, 700, 875, 1050), 150),
        _street("Illinois Ave", "Illinois Avenue", "red",
                240, (20, 100, 300, 750, 925, 1100), 150),
        _railroad("B. & O. Railroad"),                                     # 25
        _street("Atlantic Ave", "Atlantic Avenue", "yellow",
                260, (22, 110, 330, 800, 975, 1150), 150),
        _street("Ventnor Ave", "Ventnor Avenue", "yellow",
                260, (22, 110, 330, 800, 975, 1150), 150),
        _utility("Water Works"),                                           # 28
        _street("Marvin Gardens", "Marvin Gardens", "yellow",
                280, (24, 120, 360, 850, 1025, 1200), 150),
        _special("Go To Jail", "Go To Jail", "go_to_jail"),                # 30
        _street("Pacific Ave", "Pacific Avenue", "green",
                300, (26, 130, 390, 900, 1100, 1275), 200),
        _street("N. Carolina Ave", "North Carolina Avenue", "green",
                300, (26, 130, 390, 900, 1100, 1275), 200),
        _special("Community Chest", "Community Chest 3", "chest"),         # 33
        _street("Pennsylvania Ave", "Pennsylvania Avenue", "green",
                320, (28, 150, 450, 1000, 1200, 1400), 200),
        _railroad("Short Line"),                                           # 35
        _special("Chance", "Chance 3", "chance"),                          # 36
        _street("Park Place", "Park Place", "darkblue",
                350, (35, 175, 500, 1100, 1300, 1500), 200),
        _special("Luxury Tax", "Luxury Tax", "tax", 75),                   # 38
        _street("Boardwalk", "Boardwalk", "darkblue",
                400, (50, 200, 600, 1400, 1700, 2000), 200),              # 39
    ]


SQUARES = _squares()
for i, sq in enumerate(SQUARES):
    sq["idx"] = i

GROUP_MEMBERS = {}
for sq in SQUARES:
    if sq["type"] == "street":
        GROUP_MEMBERS.setdefault(sq["group"], []).append(sq["idx"])

HOUSE_LIMIT = 32
HOTEL_LIMIT = 12
