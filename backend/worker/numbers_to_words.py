import re

# Rečnici za kardinalne brojeve
JEDNOCIFRENI = {
    0: "nula", 1: "jedan", 2: "dva", 3: "tri", 4: "četiri",
    5: "pet", 6: "šest", 7: "sedam", 8: "osam", 9: "devet"
}

TINEJDZERI = {
    10: "deset", 11: "jedanaest", 12: "dvanaest", 13: "trinaest", 14: "četrnaest",
    15: "petnaest", 16: "šesnaest", 17: "sedamnaest", 18: "osamnaest", 19: "devetnaest"
}

DESETICE = {
    20: "dvadeset", 30: "trideset", 40: "četrdeset", 50: "pedeset",
    60: "šezdeset", 70: "sedamdeset", 80: "osamdeset", 90: "devedeset"
}

STOTINE = {
    100: "sto", 200: "dvesta", 300: "trista", 400: "četiristo", 500: "petsto",
    600: "šeststo", 700: "sedamsto", 800: "osamsto", 900: "devetsto"
}

# Rečnici za redne brojeve (samo zadnji deo broja se pretvara u redni)
ORDINAL_JEDNOCIFRENI = {
    0: "nulti", 1: "prvi", 2: "drugi", 3: "treći", 4: "četvrti",
    5: "peti", 6: "šesti", 7: "sedmi", 8: "osmi", 9: "deveti"
}

ORDINAL_TINEJDZERI = {
    10: "deseti", 11: "jedanaesti", 12: "dvanaesti", 13: "trinaesti", 14: "četrnaesti",
    15: "petnaesti", 16: "šesnaesti", 17: "sedamnaesti", 18: "osamnaesti", 19: "devetnaesti"
}

ORDINAL_DESETICE = {
    20: "dvadeseti", 30: "trideseti", 40: "četrdeseti", 50: "pedeseti",
    60: "šezdeseti", 70: "sedamdeseti", 80: "osamdeseti", 90: "devedeseti"
}

ORDINAL_STOTINE = {
    100: "stoti", 200: "dvestoti", 300: "tristoti", 400: "četiristoti", 500: "petstoti",
    600: "šeststoti", 700: "sedamstoti", 800: "osamstoti", 900: "devetstoti"
}

def num_to_words_sr(n: int, ordinal: bool = False) -> str:
    """
    Konvertuje ceo broj od 0 do 9999 u srpske reči (ekavica).
    Podržava i redne brojeve (ordinal=True).
    """
    if n < 0 or n > 9999:
        return str(n) # Van opsega vraća cifre

    if n == 0:
        return ORDINAL_JEDNOCIFRENI[0] if ordinal else JEDNOCIFRENI[0]

    parts = []

    # Hiljade
    thousands = n // 1000
    remainder = n % 1000

    if thousands > 0:
        if thousands == 1:
            parts.append("hiljada" if remainder == 0 and ordinal else "hiljadu")
        elif thousands == 2:
            parts.append("dve hiljade")
        elif thousands in [3, 4]:
            parts.append(f"{JEDNOCIFRENI[thousands]} hiljade")
        else:
            parts.append(f"{JEDNOCIFRENI[thousands]} hiljada")

    # Stotine
    hundreds = remainder // 100
    remainder = remainder % 100

    if hundreds > 0:
        if remainder == 0 and ordinal:
            # Ako je ceo broj npr. 300.
            parts.append(ORDINAL_STOTINE[hundreds * 100])
        else:
            parts.append(STOTINE[hundreds * 100])

    # Desetice i jedinice
    if remainder > 0:
        if remainder < 10:
            if ordinal:
                parts.append(ORDINAL_JEDNOCIFRENI[remainder])
            else:
                parts.append(JEDNOCIFRENI[remainder])
        elif remainder < 20:
            if ordinal:
                parts.append(ORDINAL_TINEJDZERI[remainder])
            else:
                parts.append(TINEJDZERI[remainder])
        else:
            tens = (remainder // 10) * 10
            units = remainder % 10

            if units == 0:
                if ordinal:
                    parts.append(ORDINAL_DESETICE[tens])
                else:
                    parts.append(DESETICE[tens])
            else:
                parts.append(DESETICE[tens])
                if ordinal:
                    parts.append(ORDINAL_JEDNOCIFRENI[units])
                else:
                    parts.append(JEDNOCIFRENI[units])
    else:
        # Ako je remainder bio 0, a imamo hiljade bez stotina
        if n % 1000 == 0 and thousands > 0 and ordinal:
            # Specijalno za npr. 2000. -> "dvehiljaditi"
            # Ali za jednostavnost, modifikujemo zadnju reč
            if thousands == 1:
                return "hiljaditi"
            elif thousands == 2:
                return "dvehiljaditi"
            else:
                return f"{JEDNOCIFRENI[thousands]}hiljaditi"

    return " ".join(parts)

def convert_numbers_to_words(text: str) -> str:
    """
    Pronalazi sve brojeve, procente i redne brojeve u tekstu
    i zamenjuje ih rečima na srpskom jeziku.
    """
    if not text:
        return text

    # 1. Zamena procenata (npr. 5% ili 5 % -> pet posto)
    def repl_percent(match):
        num = int(match.group(1))
        words = num_to_words_sr(num)
        return f"{words} posto"

    text = re.sub(r'\b(\d+)\s*%', repl_percent, text)

    # 2. Zamena rednih brojeva (npr. 1. ili 2026. -> prvi, dve hiljade dvadeset šesti)
    # Ignorišemo tačke koje su na kraju rečenice, osim ako ispred njih stoji broj
    def repl_ordinal(match):
        num = int(match.group(1))
        # Izbegavamo prevođenje decimalnih brojeva sa tačkom ovde
        words = num_to_words_sr(num, ordinal=True)
        return words

    text = re.sub(r'\b(\d+)\.(?=\s|[a-zA-ZđžćčšĐŽĆČŠ]|$)', repl_ordinal, text)

    # 3. Zamena kardinalnih brojeva (npr. 25 -> dvadeset pet)
    def repl_cardinal(match):
        num = int(match.group(1))
        words = num_to_words_sr(num)
        return words

    text = re.sub(r'\b(\d+)\b', repl_cardinal, text)

    return text
