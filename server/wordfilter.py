"""Blocks swearing, slurs and rude slang in anything new people type (names, challenges, reports).

Covers English, Arabic (Arabic script and "Arabizi" written in Latin letters), Hindi/Urdu,
Malayalam and Tamil (in their own scripts and as typed in English letters: "Manglish" and
"Tanglish") slang, with the usual disguises: CaPiTaLs, l33t numbers and symbols, dots or spaces between
letters (f.u.c.k, f u c k), repeated letters (fuuuck), accents and Arabic diacritics.

Real names must keep working, so there are two lists:
  ANYWHERE   long, unmistakable words, blocked even hidden inside other letters;
  WHOLE_WORD short or ambiguous words, blocked only as a word on their own
             ("Hassan", "Dickson", "Shitanshu", "pedometer", "crisis" all pass).
The words below are listed only so they can be blocked. Extend the lists here.
"""
import re
import unicodedata

ANYWHERE = (
    # English
    "fuck", "fuuck", "fvck", "phuck", "motherf", "mutherf", "cunt", "bitch", "biatch", "whore",
    "slut", "nigger", "nigga", "faggot", "fagot", "retard", "wanker", "bastard", "bollock",
    "asshole", "arsehole", "dickhead", "cocksuck", "pussy", "dildo", "porno", "pornhub",
    "blowjob", "handjob", "jerkoff", "shithead", "bullshit", "horseshit", "dumbass", "jackass",
    "goddamn", "rapist", "hitler", "terrorist", "sexy",
    # Hindi / Urdu
    "madarchod", "maderchod", "madarchot", "behenchod", "bhenchod", "benchod", "bhenchot",
    "chutiya", "chutiye", "chootiya", "bhosdi", "bhosda", "bhosad", "gandu", "harami", "haraami",
    "lavda", "jhaat", "randwa",
    # Arabizi
    "sharmoot", "sharmout", "sharmut", "manyook", "manyouk", "kosomak", "kussomak", "kosommak",
    "kusomak", "ibnelkalb", "yel3an", "yil3an", "khawal", "metnak", "mitnak", "zebbi",
    # Arabic script
    "شرموط", "منيوك", "متناك", "قحبه", "كسمك", "كساختك", "ابنالكلب", "يلعن",
    # Malayalam typed in English letters
    "thayoli", "thayolli", "thaayoli", "poorimon", "poorimakan", "kazhuveri", "kazhuveriy",
    "myrandi", "pundachi", "koothichi", "kunnappan",
    # Tamil typed in English letters
    "thevidiya", "thevdiya", "thevudiya", "thevadiya", "pundamavan", "pundaimavan", "pundaimagan",
    "othalaka", "oththalaka",
    # Malayalam script
    "തായോളി", "പൂറി", "കുണ്ണ", "ഊമ്പ", "കഴുവേറി", "പൂറിമോൻ",
    # Tamil script
    "தேவிடியா", "தேவடியா", "தேவுடியா", "புண்டை", "ஓத்தா",
)

WHOLE_WORD = (
    # English
    "fuk", "fck", "fk", "ass", "arse", "shit", "shite", "crap", "cock", "piss", "damn",
    "hell", "fag", "fags", "tit", "tits", "boob", "boobs", "nude", "nudes", "sex", "porn", "cum",
    "jizz", "wtf", "stfu", "milf", "thot", "hoe", "hoes", "prick", "twat", "pedo", "paedo",
    "nazi", "isis", "kkk", "idiot", "stupid", "dumb", "moron", "loser", "ugly", "kill", "suicide",
    "drugs", "weed", "vodka",
    # Hindi / Urdu
    "chut", "gand", "gaand", "loda", "lode", "lodu", "lauda", "saala", "saali", "kutta",
    "kuttiya", "kamina", "kamine",
    # Arabizi
    "kos", "kus", "kuss", "zeb", "zob", "zbi", "kalb", "7mar", "hmar", "a7a", "khara", "5ara",
    "5ra", "ars", "3ars", "ayre", "ayri",
    # Arabic script
    "كس", "زب", "زبي", "زبك", "كلب", "حمار", "حيوان", "غبي", "عبيط", "خول", "عرص", "خرا", "تفو",
    "لعنة", "لعنه", "قحبة",
    # Malayalam typed in English letters (short, so whole words only: "Kunnath" and
    # "Kunnamkulam" stay fine). "sunni" is left out on purpose: it would block Sunni Islam.
    "kunna", "kunne", "pooru", "poore", "poorr", "myre", "myru", "mairu", "maire", "myran",
    "mairan", "oombi", "oombu", "oomb", "oombal", "kundi", "koothi", "thendi", "naayinte",
    "nayinte", "pottan",
    # Tamil typed in English letters
    "otha", "oththa", "ommala", "punda", "pundai", "sootha", "soothu", "baadu", "naaye", "loosu",
    "pottai", "mayiru", "mayir", "mayire", "koodhi",
    # Malayalam script
    "മൈര്", "മൈരെ", "മൈരേ", "മൈരൻ", "പൂറ്", "കൂതി", "നായിന്റെ",
    # Tamil script
    "மயிரு", "மயிர்", "கூதி", "சூத்து", "பொட்டை", "ஓம்பு", "ஒம்மால",
)

# Words that are rude in one language but real names in another ("Dick", "Randi", "Kundan").
# In a name someone picks for themselves they are allowed, but the person stays off the
# leaderboards until an admin approves the name (Admin > Reports: "Possible real name").
# Anywhere else (challenge titles, report notes) they are blocked like WHOLE_WORD.
REVIEW = (
    "dick", "fanny", "willy", "randi", "lund", "gay", "kundan", "andi", "patti", "myra", "pooran",
)

_LEET = str.maketrans({"0": "o", "1": "i", "!": "i", "|": "i", "3": "e", "4": "a", "@": "a",
                       "5": "s", "$": "s", "7": "t", "8": "b", "9": "g", "+": "t", "€": "e"})
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و",
                              "ئ": "ي", "ـ": ""})
# Malayalam chillu letters can be typed as one character or as consonant + virama (+ ZWJ):
# fold them to one form so both spellings match.
_CHILLU = str.maketrans({"ൺ": "ണ്", "ൻ": "ന്", "ർ": "ര്", "ൽ": "ല്", "ൾ": "ള്", "ൿ": "ക്",
                         "\u200c": "", "\u200d": ""})
_INDIC = ("\u0b80", "\u0d7f")   # Tamil to Malayalam: their vowel signs are part of the word
_WORD = re.compile(r"[a-z0-9ء-ي\u0b80-\u0bff\u0d00-\u0d7f]+")


def _plain(text):
    """Lower case, no accents, no Arabic diacritics, Arabic letter variants folded.
    Tamil and Malayalam vowel signs are kept (dropping them would change the word)."""
    text = unicodedata.normalize("NFKD", (text or "").lower().translate(_CHILLU))
    text = "".join(ch for ch in text
                   if not unicodedata.combining(ch) or _INDIC[0] <= ch <= _INDIC[1])
    text = re.sub(r"[ً-ٰٟـ]", "", text)
    return text.translate(_ARABIC_FOLD)


def _squeeze(word):
    """fuuuuck -> fuck, shiiit -> shit (a letter repeated 3+ times counts once)."""
    return re.sub(r"(.)\1{2,}", r"\1", word)


def _variants(text):
    """Ways of reading the text: as typed (keeps Arabizi digits) and with l33t undone."""
    plain = _plain(text)
    return (plain, plain.translate(_LEET))


_ANY = tuple(_plain(w).replace(" ", "") for w in ANYWHERE)
_WHOLE = {_plain(w) for w in WHOLE_WORD}
_REVIEW = {_plain(w) for w in REVIEW}


def _short_word_runs(words):
    """'f u c k', 'f.u.c.k' or 'fu ck': join each run of 2+ very short words (3 letters or
    fewer). Long words are never joined, so two real names can't add up to a bad word."""
    runs, cur = [], []
    for w in words + [""]:
        if 0 < len(w) <= 3:
            cur.append(w)
        else:
            if len(cur) >= 2:
                runs.append("".join(cur))
            cur = []
    return runs


def find_blocked(text):
    """The first blocked word in text, or None."""
    if not text or not text.strip():
        return None
    for version in _variants(text):
        words = _WORD.findall(version)
        candidates = words + _short_word_runs(words)
        for w in candidates:
            if w in _WHOLE or _squeeze(w) in _WHOLE:
                return w
        for w in candidates:
            for bad in _ANY:
                if bad in w or bad in _squeeze(w):
                    return bad
    return None


def is_clean(text):
    return find_blocked(text) is None


def check(text, what="That"):
    """Raise ValueError if the text contains a blocked word. `what` names the field.
    Maybe-real names (REVIEW) are blocked here too: this is for titles and notes, not names."""
    if find_blocked(text) or needs_review(text):
        raise ValueError(f"{what} has a word that isn't allowed on StrideBoard. Please choose another")


def needs_review(text):
    """For names: the word that might be rude but might be a real name (e.g. 'dick'), or None."""
    for version in _variants(text or ""):
        for w in _WORD.findall(version):
            if w in _REVIEW or _squeeze(w) in _REVIEW:
                return w
    return None


def check_name(text, what="That name"):
    """Like check(), for a name someone picks: blocked words are refused; maybe-real names pass
    (the caller holds them for an admin with needs_review)."""
    if find_blocked(text):
        raise ValueError(f"{what} has a word that isn't allowed on StrideBoard. Please choose another")

