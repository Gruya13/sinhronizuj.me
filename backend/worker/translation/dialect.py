import re
from backend.worker.numbers_to_words import convert_numbers_to_words

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    # Podrška i za <think> (DeepSeek) i za <thought> (Qwen)
    for tag in ["think", "thought"]:
        text = re.sub(rf'<{tag}>.*?</{tag}>', '', text, flags=re.DOTALL)
        
    for tag in ["think", "thought"]:
        start_tag = f"<{tag}>"
        if start_tag in text:
            idx = text.find(start_tag)
            # Ako je tag na početku, a dalje imamo JSON/strukturu, uzmi je od prve otvorene zagrade
            valid_braces = [pos for pos in [text.find('{'), text.find('[')] if pos != -1]
            if valid_braces:
                first_valid_brace = min(valid_braces)
                if first_valid_brace > idx:
                    text = text[first_valid_brace:]
                    continue
            text = text.split(start_tag)[0]
    return text.strip()

def clean_translation_text(text: str) -> str:
    if not text:
        return text
    
    # 1. Padeži za Ej Aj
    text = re.sub(r'\bsa Ej Aj\b', 'sa Ej Ajem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj\b', 'o Ej Aju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bod Ej Aj\b', 'od Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bu Ej Aj\b', 'u Ej Aju', text, flags=re.IGNORECASE)
    
    # 2. Greške sa "buduće" umesto "budućnost"
    text = re.sub(r'\bžele ovo buduće\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžele to buduće\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bovo buduće\b', 'ovu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bto buduće\b', 'tu budućnost', text, flags=re.IGNORECASE)
    
    # 3. Tipične greške u izgovoru/kucanju za "poći po zlu"
    text = re.sub(r'\bpođi po zlu\b', 'poći po zlu', text, flags=re.IGNORECASE)
    
    # 4. Množina robotike i slično
    text = re.sub(r'\brobotikama\b', 'robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\brobotike\b', 'roboticu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aju i robotike\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj i robotike\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj i robotikama\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aju i robotikama\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    
    # 5. Odluke o pripremi/prijemu -> zapošljavanju (u svim padežima)
    text = re.sub(r'\bodluk([a-z]*) o (pripremi|prijemu)\b', r'odluk\1 o zapošljavanju', text, flags=re.IGNORECASE)
    
    # 6. Slaganje rodova za knjige (poput X i Y, koji su popularni -> koje su popularne)
    text = re.sub(r'\bpoput ([^,]+) i ([^,]+), koji su popularni\b', r'poput \1 i \2, koje su popularne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoput ([^,]+), koji su popularni\b', r'poput \1, koje su popularne', text, flags=re.IGNORECASE)
    
    # 7. Ispravka povratnog "se" kod glagola postati (npr. "koje su se ironično postale popularne" -> "koje su ironično postale popularne")
    text = re.sub(r'\b(su|je) se\s+([^,.]+?\s+)?(postale|postali|postala|postao|postalo)\b', r'\1 \2\3', text, flags=re.IGNORECASE)
    
    # 8. Ispravka neobičnih opisa zidova (na zadnjoj zidini -> na zadnjem zidu)
    text = re.sub(r'\bna zadnjoj zidini\b', 'na zadnjem zidu', text, flags=re.IGNORECASE)
    
    # 9. Osnivačka dokumenta (članke o firmi kako bi je registrovala -> dokumente za registraciju kako bi registrovala firmu)
    text = re.sub(r'\bčlanke o firmi kako bi je registrovala\b', 'dokumente za registraciju kako bi registrovala firmu', text, flags=re.IGNORECASE)
    
    # 10. Prirodniji raspored reči za negaciju nužnosti i redosled
    text = re.sub(r'\bne nužno (rade|čine)\b', r'ne \1 nužno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bda to ne nužno čine\b', 'da to ne čine nužno', text, flags=re.IGNORECASE)
    
    # 11. Ispravka nepravilnog 'zabrinu o riziku' -> 'zabrinuti zbog rizika'
    text = re.sub(r'\bkoji se (zabrinu|zabrinjavaju|zabrinjuju) o riziku\b', 'koji su zabrinuti zbog rizika', text, flags=re.IGNORECASE)

    # 14. Ispravka "žele ovo budućnost" -> "žele takvu budućnost"
    text = re.sub(r'\bžele ovo budućnost\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    
    # 15. Ispravka "pođeti po zlu" -> "poći po zlu"
    text = re.sub(r'\bpođeti po zlu\b', 'poći po zlu', text, flags=re.IGNORECASE)
    
    # 16. Ispravka "pratite za više" -> "prati za više" (usklađivanje ti/vi obraćanja)
    text = re.sub(r'\bpratite za više\b', 'prati za više', text, flags=re.IGNORECASE)

    # 17. Ispravka futura I sa "će" (hrvatski / ijekavski oblici: radit će -> radiće, raditi će -> radiće)
    # Koristimo whitelistu glagolskih osnova kako bismo sprečili kvarenje imenica poput put, internet, sat, sajt
    VERB_STEMS = [
        'radi', 'bi', 'ima', 'hte', 'htje', 'vidje', 'vide', 'živje', 'žive',
        'razumje', 'razume', 'djelova', 'delova', 'riješi', 'reši', 'promijeni',
        'promeni', 'primijeti', 'primeti', 'stavi', 'krenu', 'izreza', 'savi',
        'koristi', 'napravi', 'poveza', 'prati', 'skrati', 'otvori', 'zatvori',
        'posta', 'poče', 'nauči', 'peva', 'pisa', 'čita', 'diza', 'traži', 'kupi',
        'proda', 'plaća', 'plati', 'posla', 'spreči', 'spriječi', 'deli', 'dijeli',
        'brusi', 'šmirgla', 'zavari', 'hefta', 'obmota', 'presiječe', 'preseče',
        'odsiječe', 'odseče', 'isiječe', 'iseče', 'savije', 'postane', 'postigi', 'postig'
    ]
    pattern_stems = '|'.join(VERB_STEMS)
    text = re.sub(
        rf'\b({pattern_stems})ti?\s+(ću|ćeš|će|ćemo|ćete)\b',
        lambda m: f"{m.group(1)}{m.group(2)}",
        text,
        flags=re.IGNORECASE
    )

    # 18. Morfološke i sintaksičke ispravke (na osnovu evaluacije)
    text = re.sub(r'\bjednake cilindri\b', 'jednake cilindriće', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsecu tradicionalne\b', 'seku tradicionalne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvenog komad\b', 'drveni komad', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkomad drvenog\b', 'komad drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvene podloge\b', 'drvene osnove', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvenog podloge\b', 'drvene osnove', text, flags=re.IGNORECASE)
    text = re.sub(r'\bna razmeru koju\b', 'u razmeri koju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bna razmeru\b', 'u razmeri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bZavar je glatko\b', 'Zavar je gladak', text, flags=re.IGNORECASE)
    text = re.sub(r'\bglatko izgleda\b', 'gladak izgled', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnavojni štap montaža\b', 'montažni štap sa navojem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnavojnog štapa montaža\b', 'montažnog štapa sa navojem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofanje\b', 'brušenje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofanja\b', 'brušenja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofati\b', 'brusiti', text, flags=re.IGNORECASE)

    # 18.5 Dodatna stilska čišćenja za Ej Aj i neprirodne fraze
    text = re.sub(r'\bEj-Aj\b', 'Ej Aj', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEj-Aja\b', 'Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEj-Aju\b', 'Ej Aju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEj-Ajem\b', 'Ej Ajem', text, flags=re.IGNORECASE)
    
    # Neprirodne kolokvijalne fraze
    text = re.sub(r'\bpostaje ludo\b', 'postaje zanimljivo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpostaju lude\b', 'postaju zanimljive', text, flags=re.IGNORECASE)
    text = re.sub(r'\bludo je kako\b', 'neverovatno je kako', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstvari postaju lude\b', 'stvari postaju zanimljive', text, flags=re.IGNORECASE)
    text = re.sub(r'\bovde postaje ludilo\b', 'ovde situacija postaje zanimljiva', text, flags=re.IGNORECASE)

    # 18.8 Sistemsko čišćenje ijekavizama i regionalizama (Leak Guard)
    text = re.sub(r'\bdio\b', 'deo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdijel(ovi|ove|u|om|a|ova|ima)\b', r'del\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdijel(i|e|iti|imo|ite|io|ila|ili|iće)\b', r'del\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btijekom\b', 'tokom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsustav\b', 'sistem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsustav(i|a|u|om|ima|ove)\b', r'sistem\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btjedan\b', 'nedelja', text, flags=re.IGNORECASE)
    text = re.sub(r'\btjedn(a|u|om|e|i|ima)\b', r'nedeljn\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btisuća\b', 'hiljada', text, flags=re.IGNORECASE)
    text = re.sub(r'\btisuć(e|u|om|i|ama)\b', r'hiljad\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\buvjet\b', 'uslov', text, flags=re.IGNORECASE)
    text = re.sub(r'\buvjet(i|a|u|om|ima|ove)\b', r'uslov\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\butjecaj\b', 'uticaj', text, flags=re.IGNORECASE)
    text = re.sub(r'\butjecaj(i|a|u|om|ima|ove)\b', r'uticaj\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsučelje\b', 'interfejs', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsučelj(a|u|em|ima|e)\b', r'interfejs\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bzaslon\b', 'ekran', text, flags=re.IGNORECASE)
    text = re.sub(r'\bzaslon(i|a|u|om|ima|ove)\b', r'ekran\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btipkovnica\b', 'tastatura', text, flags=re.IGNORECASE)
    text = re.sub(r'\btipkovnic(e|i|u|om|ama)\b', r'tastatur\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoveznica\b', 'link', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoveznic(u|om)\b', r'link\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoveznice\b', 'linkovi', text, flags=re.IGNORECASE)
    text = re.sub(r'\buvijek\b', 'uvek', text, flags=re.IGNORECASE)
    text = re.sub(r'\bgdje\b', 'gde', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvidjeti\b', 'videti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvidje(o|la|li|le)\b', r'vide\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bspriječiti\b', 'sprečiti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bspriječi(o|la|li|le|ti|mo|te)\b', r'spreči\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpromijeniti\b', 'promeniti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpromijeni(o|la|li|le|ti|mo|te)\b', r'promeni\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\briješiti\b', 'rešiti', text, flags=re.IGNORECASE)
    text = re.sub(r'\briješi(o|la|li|le|ti|mo|te)\b', r'reši\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bprimijetiti\b', 'primetiti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bprimijeti(o|la|li|le|ti|mo|te)\b', r'primeti\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkaos\b', 'haos', text, flags=re.IGNORECASE)
    text = re.sub(r'\bučinkovitost\b', 'efikasnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bučinkovit(a|o|i|e|u|om)\b', r'efikasn\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btvrtk(a|e|i|u|om|ama)\b', r'firm\1', text, flags=re.IGNORECASE)

    # 19. Deterministička konverzija brojeva u reči
    text = convert_numbers_to_words(text)

    # 20. Dupli razmaci i čišćenje
    text = re.sub(r'\s+', ' ', text).strip()
    return text
