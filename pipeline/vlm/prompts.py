"""Промпты VLM. Ответ — строго JSON, чтобы логика решений была в коде, а не в свободном тексте модели."""

SCAN = """A frame from a ceiling CCTV camera, cropped around a bank cashier's desk
(the desk with a banknote counting machine and a laptop). The cashier is the employee who works seated at this desk;
clients may sit or stand on the opposite side of the desk.
Answer ONLY JSON:
{"cashier_at_desk": true/false,
 "cashier_holds": "phone" | "food" | "drink" | "banknotes" | "documents" | "bag" | "nothing" | "other",
 "uses_mobile_phone": true/false,
 "eats_or_drinks": true/false}"""

PERSON = """A zoomed crop of one person at a bank cashier's desk, from a ceiling CCTV camera.
Look at the person's hands and face. Answer ONLY JSON:
{"holds_mobile_phone": true/false, "eats": true/false, "drinks": true/false,
 "hands": "what is in the person's hands, <= 8 words"}"""

PRESENCE = """A frame from a ceiling CCTV camera, cropped around a bank cashier's desk.
Is the cashier seated or standing at the working side of this desk right now (not walking away, not at the door)?
Answer ONLY JSON: {"cashier_at_desk": true/false}"""

DESK = """This is a zoomed crop of a bank cashier's desk from a ceiling CCTV camera. The cashier has left.
Fixed equipment that does NOT count: banknote counting machine, laptop, desk telephone, cables.
List what else lies on the desk surface. Answer ONLY JSON:
{"banknotes_or_cash": true/false, "cash_bag_or_sack": true/false, "personal_bag_or_clothes": true/false,
 "food_or_drink": true/false, "tablet_or_papers": true/false, "laptop_screen_lit": true/false,
 "other_items": "short list"}"""

SCREEN = """A zoomed crop of a laptop on a bank cashier's desk from a ceiling CCTV camera. The cashier has left the desk.
What does the laptop screen show?
- "application": a working program with data (spreadsheet, table, document, white window with text/rows);
- "lock_screen": a Windows lock/login screen or desktop wallpaper (landscape picture, clock), no working window;
- "off": the screen is black/off or the lid is closed.
Answer ONLY JSON: {"screen": "application" | "lock_screen" | "off", "evidence": "<= 12 words"}"""

PHONE = """Image 1: a bank cashier's workplace from a ceiling CCTV camera. Images 2-3: zoom on one person
from image 1, taken 1 second apart.
Is this person holding or using a personal mobile phone / smartphone?
A smartphone is a rigid flat slab with a screen (the screen may be lit). Banknotes — folded or fanned out in the hand —
paper documents, bank cards, a calculator or a desk telephone handset do NOT count.
Answer ONLY JSON: {"mobile_phone_in_hands": true/false, "evidence": "what exactly is visible, <= 15 words"}"""

ROLE = """A frame from a ceiling CCTV camera in a bank cash room. People at the desk are marked with labelled boxes.
Which marked person is the bank cashier — the employee who works at this desk (operates the banknote counting machine
and the laptop, sits in the employee's chair)? The others are clients, collectors or visitors.
Answer ONLY JSON: {"cashier": "<label of the box>", "why": "<= 12 words"}"""

EAT = """Image 1: a bank cashier's workplace from a ceiling CCTV camera. Images 2-3: zoom on one person
from image 1, taken 1 second apart.
Is this person eating food or drinking (cup, bottle, can)? Holding banknotes or documents does NOT count.
Answer ONLY JSON: {"eats": true/false, "drinks": true/false, "evidence": "what exactly is visible, <= 15 words"}"""
