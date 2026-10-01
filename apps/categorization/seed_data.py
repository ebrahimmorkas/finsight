"""Labelled examples for the starter model used before a user has enough data.

Descriptions are generated from merchant names and the kind of noise real bank
exports contain (store numbers, references, city/state suffixes), so the model
learns to look past it. Labels are names of the default categories.
"""

import random

MERCHANTS = {
    "Groceries": [
        "TESCO STORES",
        "SAINSBURYS",
        "WHOLE FOODS MARKET",
        "TRADER JOES",
        "KROGER",
        "ALDI",
        "LIDL",
        "SAFEWAY",
        "COSTCO WHSE",
        "WALMART GROCERY",
        "CARREFOUR",
        "MORRISONS",
        "WAITROSE",
    ],
    "Dining": [
        "STARBUCKS",
        "MCDONALDS",
        "CHIPOTLE",
        "PRET A MANGER",
        "DOMINOS PIZZA",
        "SUBWAY",
        "UBER EATS",
        "DELIVEROO",
        "DOORDASH",
        "NANDOS",
        "COSTA COFFEE",
        "BURGER KING",
        "KFC",
    ],
    "Transport": [
        "UBER TRIP",
        "LYFT RIDE",
        "SHELL OIL",
        "BP FUEL",
        "TFL TRAVEL",
        "EXXONMOBIL",
        "CHEVRON",
        "BOLT RIDE",
        "TRAINLINE",
        "NATIONAL RAIL",
        "PARKING METER",
        "CITYMAPPER",
    ],
    "Rent & Housing": [
        "RENT PAYMENT",
        "LANDLORD STANDING ORDER",
        "MORTGAGE PAYMENT",
        "HOA DUES",
        "IKEA",
        "HOME DEPOT",
        "B&Q",
        "LETTING AGENT",
    ],
    "Utilities": [
        "BRITISH GAS",
        "EDF ENERGY",
        "COMCAST",
        "VERIZON",
        "AT&T",
        "THAMES WATER",
        "OCTOPUS ENERGY",
        "VODAFONE",
        "PG&E",
        "COUNCIL TAX",
    ],
    "Shopping": [
        "AMAZON MKTP",
        "AMZN MKTP",
        "EBAY",
        "ZARA",
        "H&M",
        "UNIQLO",
        "TARGET",
        "BEST BUY",
        "ARGOS",
        "ASOS",
        "APPLE STORE",
        "ETSY",
    ],
    "Entertainment": [
        "CINEWORLD",
        "AMC THEATRES",
        "STEAM GAMES",
        "PLAYSTATION NETWORK",
        "TICKETMASTER",
        "NINTENDO ESHOP",
        "BOWLING",
        "ODEON CINEMAS",
    ],
    "Health": [
        "BOOTS PHARMACY",
        "CVS PHARMACY",
        "WALGREENS",
        "PUREGYM",
        "DENTAL CARE",
        "PLANET FITNESS",
        "SPECSAVERS",
        "NHS PRESCRIPTION",
    ],
    "Subscriptions": [
        "NETFLIX",
        "SPOTIFY",
        "DISNEY PLUS",
        "YOUTUBE PREMIUM",
        "ICLOUD STORAGE",
        "ADOBE",
        "MICROSOFT 365",
        "AMAZON PRIME",
        "HBO MAX",
        "DROPBOX",
        "CHATGPT PLUS",
        "AUDIBLE",
    ],
    "Travel": [
        "RYANAIR",
        "EASYJET",
        "BRITISH AIRWAYS",
        "AIRBNB",
        "BOOKING.COM",
        "HILTON HOTELS",
        "MARRIOTT",
        "EXPEDIA",
        "DELTA AIR",
        "UNITED AIRLINES",
        "HERTZ RENTAL",
    ],
    "Salary": [
        "PAYROLL",
        "SALARY",
        "ACME CORP PAYROLL",
        "DIRECT DEP",
        "WAGES",
        "MONTHLY SALARY",
    ],
    "Other income": ["INTEREST PAID", "REFUND", "CASHBACK", "DIVIDEND", "TAX REFUND"],
    "Transfers": [
        "TRANSFER TO SAVINGS",
        "TRANSFER FROM CHECKING",
        "VENMO",
        "PAYPAL TRANSFER",
        "ZELLE",
        "REVOLUT TOPUP",
        "CREDIT CARD PAYMENT",
    ],
}

INCOME = {"Salary", "Other income"}
CITIES = ["LONDON", "SEATTLE WA", "NEW YORK NY", "AUSTIN TX", "MANCHESTER", "BERLIN", ""]


def _noisy(merchant: str, rng: random.Random) -> str:
    variants = [
        merchant,
        f"{merchant} #{rng.randint(100, 9999)}",
        f"POS {merchant} {rng.choice(CITIES)}",
        f"{merchant}*{rng.randint(10000, 99999):X} {rng.choice(CITIES)}",
        f"CARD PURCHASE {merchant} {rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}",
    ]
    return rng.choice(variants).strip()


def generate(samples_per_category: int = 40, seed: int = 7) -> list[tuple[str, float, str]]:
    """Return ``(description, amount, category_name)`` examples."""
    rng = random.Random(seed)
    rows = []
    for category, merchants in MERCHANTS.items():
        for _ in range(samples_per_category):
            amount = round(rng.uniform(5, 3000 if category in INCOME else 120), 2)
            sign = 1 if category in INCOME else -1
            rows.append((_noisy(rng.choice(merchants), rng), sign * amount, category))
    return rows
