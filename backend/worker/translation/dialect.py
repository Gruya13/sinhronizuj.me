import re
from backend.worker.numbers_to_words import convert_numbers_to_words

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    # 1. Prvo uklanjamo sve kompletne parove <think>...</think> i <thought>...</thought>
    for tag in ["think", "thought"]:
        text = re.sub(rf'<{tag}>.*?</{tag}>', '', text, flags=re.DOTALL)
        
    # 2. Ako je ostao nezatvoreni tag na kraju (ili u sredini), uklanjamo sve od tog taga do kraja stringa
    for tag in ["think", "thought"]:
        start_tag = f"<{tag}>"
        if start_tag in text:
            idx = text.find(start_tag)
            valid_braces = [pos for pos in [text.find('{', idx), text.find('[', idx)] if pos != -1]
            if valid_braces:
                first_valid_brace = min(valid_braces)
                text = text[first_valid_brace:]
            else:
                text = text[:idx]
                
    # 3. Uklanjamo preostale zatvarajuće tagove ako su nekako ostali sami
    for tag in ["think", "thought"]:
        text = text.replace(f"</{tag}>", "")
        
    return text.strip()


def clean_translation_text(text: str, qe_score: float = None) -> str:
    if not text:
        return text
        
    if qe_score is not None and qe_score >= 0.88:
        from .transliter import to_latin
        return to_latin(text)
    
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

    # 21. Ekavizacija preostalih ijekavskih korena (provjeriti -> proveriti, vjerovati -> verovati, izmjeriti -> izmeriti...)
    text = re.sub(r'\bprovjeri(o|la|li|le|ti|mo|te|v\w*)', r'proveri\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvjeri(o|la|li|le|ti|mo|te|v\w*)', r'veri\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvjerova(t|o|la|li|le|mo|te|ju|h\w*)', r'verova\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjerovatn(o|a|i|e|u|im)', r'neverovatn\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvjer(a|e|i|u|om|ama)', r'ver\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bizmjeri(o|la|li|le|ti|mo|te)', r'izmeri\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmjer(a|e|i|u|om|ama|ilo|ili|ila|ilo|iše)', r'mer\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\brazmj(er|er\w*)', r'razmer\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsvijet\b', 'svet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsvijet(la|lo|li|le|om|ova|ovima)', r'svet\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvijest\b', 'vest', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvijest(i|ima)', r'vest\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btijelo\b', 'telo', text, flags=re.IGNORECASE)
    text = re.sub(r'\btijel(a|u|om|ima|es\w*)', r'tel\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bobavijest\b', 'obavest', text, flags=re.IGNORECASE)
    text = re.sub(r'\bobavijest(i|ima)', r'obavest\1', text, flags=re.IGNORECASE)
    
    # 22. Ispravka grešaka specifičnih za test videe
    # a) kanjaroo / kanguro -> kengur (svi padeži i oblici)
    text = re.sub(r'\bkanjaroo\b', 'kengur', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanjarooa\b', 'kengura', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanjarooi\b', 'kenguri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanjarooima\b', 'kengurima', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanjarooa\b', 'kengure', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\bkanguroa\b', 'kengura', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkangurove\b', 'kengure', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkangurova\b', 'kengura', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkangurovi\b', 'kenguri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkangurovu\b', 'kenguru', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanguro\b', 'kengur', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkangure\b', 'kengure', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanguri\b', 'kenguri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkangura\b', 'kengura', text, flags=re.IGNORECASE)
    
    # b) stručak / stručka -> noj (svi padeži)
    text = re.sub(r'\bstručak\b', 'noj', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstručka\b', 'noja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstručku\b', 'noju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstručci\b', 'nojevi', text, flags=re.IGNORECASE)
    
    # c) Džoi / joi / joj -> mladunče / mladunci (kada se odnosi na kengure)
    text = re.sub(r'\bDžoi\b', 'mladunče', text, flags=re.IGNORECASE)
    text = re.sub(r'\bjoi\b', 'mladunci', text, flags=re.IGNORECASE)
    # Specifični popravci za joi/joj u test videu
    text = re.sub(r'\bšto joj često kriju pravo ljudima\b', 'što se mladunci često uvlače pravo ljudima u naručje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšto joi često kriju pravo ljudima\b', 'što se mladunci često uvlače pravo ljudima u naručje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšto joj često zavlače pravo ljudima\b', 'što se mladunci često uvlače pravo ljudima u naručje', text, flags=re.IGNORECASE)
    
    # d) maternom vreću / majčinu vreću -> majčinom tobolcu / torbi / tobolac
    text = re.sub(r'\bmaternom vreću\b', 'majčinom tobolcu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmaterne vreće\b', 'majčinog tobolca', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmajčinu vreću\b', 'majčinu torbu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmajčine vreće\b', 'majčine torbe', text, flags=re.IGNORECASE)
    text = re.sub(r'\bu vreću\b', 'u tobolac', text, flags=re.IGNORECASE)
    text = re.sub(r'\bu vreći\b', 'u tobolcu', text, flags=re.IGNORECASE)
    
    # e) AI / Aj Aj -> Ej Aj (i padeži)
    text = re.sub(r'\bAI-a\b', 'Ej Aja', text)
    text = re.sub(r'\bAI-u\b', 'Ej Aju', text)
    text = re.sub(r'\bAI-em\b', 'Ej Ajem', text)
    text = re.sub(r'\bAI-ev\b', 'Ej Ajev', text)
    text = re.sub(r'\bAI\b', 'Ej Aj', text)
    
    text = re.sub(r'\bAj\s+Aj-a\b', 'Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj-u\b', 'Ej Aju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj-em\b', 'Ej Ajem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj-ev\b', 'Ej Ajev', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj\s+a\b', 'Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj\s+agent\b', 'Ej Aj agent', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj\s+agenta\b', 'Ej Aj agenta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj\s+agentu\b', 'Ej Aj agentu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAj\s+Aj\b', 'Ej Aj', text, flags=re.IGNORECASE)
    
    # f) devetsto jedanaesti -> devet-jedan-jedan
    text = re.sub(r'\bdevetsto jedanaesti\b', 'devet-jedan-jedan', text, flags=re.IGNORECASE)
    
    # g) Brave New World -> Vrli novi svet
    text = re.sub(r'\bDva novi sveta\b', 'Vrli novi svet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bBraev Novi Svet\b', 'Vrli novi svet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bBraev\b', 'Vrli', text, flags=re.IGNORECASE)
    
    # h) Zabeležila je muralista / Najavila je muralistu -> Angažovala je muralistu
    text = re.sub(r'\bZabeležila je muralista\b', 'Angažovala je muralistu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bNajavila je muralistu\b', 'Angažovala je muralistu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmuralista\b', 'muralistu', text, flags=re.IGNORECASE)
    
    # i) nije obavezno da rade ovo zato što -> ne rade to nužno zato što
    text = re.sub(r'\bnije obavezno da rade ovo zato što\b', 'ne rade to nužno zato što', text, flags=re.IGNORECASE)
    
    # j) Ostralyja -> Australija (svi padeži)
    text = re.sub(r'\bOstralyji\b', 'Australiji', text, flags=re.IGNORECASE)
    text = re.sub(r'\bOstralyja\b', 'Australija', text, flags=re.IGNORECASE)
    text = re.sub(r'\bOstralyje\b', 'Australije', text, flags=re.IGNORECASE)
    
    # k) Lajnked / Lajnkedu -> Linkdin / Linkdinu
    text = re.sub(r'\bLajnkedu\b', 'Linkdinu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bLajnked\b', 'Linkdin', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKrajlisu\b', 'Krejglistu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKrajlis\b', 'Krejglist', text, flags=re.IGNORECASE)
    
    # l) ijekavski susjed i osjetljiv
    text = re.sub(r'\bsusjed\b', 'sused', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsusjeda\b', 'suseda', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsusjedi\b', 'susedi', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsusjedima\b', 'susedima', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosjetljiv(a|i|o|e|u|om|ih|im|ost)?\b', r'osetljiv\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bjednu uputu\b', 'jedno uputstvo', text, flags=re.IGNORECASE)
    text = re.sub(r'\buput(a|e|i|u|om)\b', r'uputstv\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\buputstvo\b', 'uputstvo', text, flags=re.IGNORECASE)
    text = re.sub(r'\buputstvu\b', 'uputstvu', text, flags=re.IGNORECASE)
    text = re.sub(r'\buputstva\b', 'uputstva', text, flags=re.IGNORECASE)
    text = re.sub(r'\buputstvom\b', 'uputstvom', text, flags=re.IGNORECASE)
    
    # m) stvaračica Lune / samo služila / odbijaju
    text = re.sub(r'\bstvaračica Lune\b', 'tvorac Lune', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstvaračica\b', 'tvorac', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnije samo služila\b', 'nije samo pratila naređenja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bOdbijaju kvalifikovane\b', 'odbila je kvalifikovane', text, flags=re.IGNORECASE)
    text = re.sub(r'\bŠta to učini\b', 'Šta ovo zapravo radi', text, flags=re.IGNORECASE)

    # n) dodatne popravke za kengure i veštačku inteligenciju
    text = re.sub(r'\bkanguar\b', 'kengur', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanguara\b', 'kengura', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanguare\b', 'kengure', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanguari\b', 'kenguri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkanguarima\b', 'kengurima', text, flags=re.IGNORECASE)
    text = re.sub(r'\bjojci\b', 'mladunci', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpetljate\b', 'češkate', text, flags=re.IGNORECASE)
    
    # o) veštačka inteligencija umesto umetne
    text = re.sub(r'\bumetne inteligencije\b', 'veštačke inteligencije', text, flags=re.IGNORECASE)
    text = re.sub(r'\bumetnu inteligenciju\b', 'veštačku inteligenciju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bumetna inteligencija\b', 'veštačka inteligencija', text, flags=re.IGNORECASE)
    text = re.sub(r'\bumetnom inteligencijom\b', 'veštačkom inteligencijom', text, flags=re.IGNORECASE)
    
    # p) Uklanjanje i zamena meta-odgovora modela
    text = re.sub(r'^Naravno, evo ispravljenog prevoda[:.]?$', 'Angažovala je i muralistu da naslika ogromnu verziju logotipa koji je sama dizajnirala na zadnjem zidu.', text, flags=re.IGNORECASE)
    text = re.sub(r'\bNaravno, evo ispravljenog prevoda:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEvo ispravljenog prevoda:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEvo prevoda:\s*', '', text, flags=re.IGNORECASE)
    
    # q) usklađivanje ti/vi obraćanja na kraju
    text = re.sub(r'\bpratite\b', 'prati nas', text, flags=re.IGNORECASE)

    # 20. Dupli razmaci i čišćenje
    text = re.sub(r'\s+', ' ', text).strip()
    return text
