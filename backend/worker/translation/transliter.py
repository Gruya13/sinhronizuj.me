import re

CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'đ', 'е': 'e', 'ж': 'ž',
    'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n',
    'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'ć', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'č', 'џ': 'dž', 'ш': 'š',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Ђ': 'Đ', 'Е': 'E', 'Ж': 'Ž',
    'З': 'Z', 'И': 'I', 'Ј': 'J', 'К': 'K', 'Л': 'L', 'Љ': 'Lj', 'М': 'M', 'Н': 'N',
    'Њ': 'Nj', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'Ћ': 'Ć', 'У': 'U',
    'Ф': 'F', 'Х': 'H', 'Ц': 'C', 'Ч': 'Č', 'Џ': 'Dž', 'Ш': 'Š',
    'ѓ': 'đ', 'ќ': 'ć', 'ѕ': 'dz', 'Ѓ': 'Đ', 'Ќ': 'Ć', 'Ѕ': 'Dz'
}

def preserve_case(match, repl):
    matched_text = match.group(0)
    if matched_text.isupper():
        return repl.upper()
    if matched_text and matched_text[0].isupper():
        return repl[0].upper() + repl[1:] if len(repl) > 1 else repl.upper()
    return repl.lower()

LATIN_REPLACEMENTS_RAW = {
    # Ijekavizmi - deo
    r'\bdio\b': 'deo',
    r'\bdijel\b': 'deo',
    r'\bdijela\b': 'dela',
    r'\bdijelu\b': 'delu',
    r'\bdijelom\b': 'delom',
    r'\bdijelovi\b': 'delovi',
    r'\bdijelove\b': 'delove',
    r'\bdijelova\b': 'delova',
    r'\bdijelovima\b': 'delovima',
    
    # spriječiti
    r'\bspriječiti\b': 'sprečiti',
    r'\bspriječio\b': 'sprečio',
    r'\bspriječila\b': 'sprečila',
    r'\bspriječilo\b': 'sprečilo',
    r'\bspriječeno\b': 'sprečeno',
    r'\bspriječeni\b': 'sprečeni',
    r'\bspriječili\b': 'sprečili',
    r'\bspriječi\b': 'spreči',
    r'\bspriječe\b': 'spreče',
    r'\bspriječivši\b': 'sprečivši',
    r'\bspriječite\b': 'sprečite',
    
    # dvjesto
    r'\bdvjesto\b': 'dvesta',
    
    # tijekom
    r'\btijekom\b': 'tokom',
    
    # tjedan i fraze
    r'\bu ovom tjednu\b': 'u ovoj nedelji',
    r'\bu tom tjednu\b': 'u toj nedelji',
    r'\bovom tjednu\b': 'ovoj nedelji',
    r'\bovog tjedna\b': 'ove nedelje',
    r'\btog tjedna\b': 'te nedelje',
    r'\bprošlog tjedna\b': 'prošle nedelje',
    r'\bprošlom tjednu\b': 'prošle nedelje',
    r'\bsledećeg tjedna\b': 'sledeće nedelje',
    r'\bsljedećeg tjedna\b': 'sledeće nedelje',
    r'\bsledećem tjednu\b': 'sledeće nedelje',
    r'\bsljedećem tjednu\b': 'sledeće nedelje',
    r'\bidućeg tjedna\b': 'sledeće nedelje',
    r'\bidućem tjednu\b': 'sledeće nedelje',
    r'\btjedan\b': 'nedelja',
    r'\btjedna\b': 'nedelje',
    r'\btjednu\b': 'nedelji',
    r'\btjednom\b': 'nedeljom',
    r'\btjedni\b': 'nedeljni',
    r'\btjedne\b': 'nedelje',
    r'\btjedana\b': 'nedelja',
    r'\btjednima\b': 'nedeljama',
    
    # sustav
    r'\bsustav\b': 'sistem',
    r'\bsustava\b': 'sistema',
    r'\bsustavu\b': 'sistemu',
    r'\bsustavom\b': 'sistemom',
    r'\bsustavi\b': 'sistemi',
    r'\bsustavima\b': 'sistemima',
    r'\bsustave\b': 'sisteme',
    
    # uvjet
    r'\buvjet\b': 'uslov',
    r'\buvjeta\b': 'uslova',
    r'\buvjetu\b': 'uslovu',
    r'\buvjetom\b': 'uslovom',
    r'\buvjeti\b': 'uslovi',
    r'\buvjetima\b': 'uslovima',
    r'\buvjete\b': 'uslove',
    
    # utjecaj
    r'\butjecaj\b': 'uticaj',
    r'\butjecaja\b': 'uticaja',
    r'\butjecaju\b': 'uticaju',
    r'\butjecajem\b': 'uticajem',
    r'\butjecaji\b': 'uticaji',
    r'\butjecajima\b': 'uticajima',
    r'\butjecaje\b': 'uticaje',
    
    # učinkovit
    r'\bučinkovit\b': 'efikasan',
    r'\bučinkovita\b': 'efikasna',
    r'\bučinkovito\b': 'efikasno',
    r'\bučinkovite\b': 'efikasne',
    r'\bučinkoviti\b': 'efikasni',
    r'\bučinkovitih\b': 'efikasnih',
    r'\bučinkovitom\b': 'efikasnom',
    r'\bučinkovitost\b': 'efikasnost',
    r'\bučinkovitosti\b': 'efikasnosti',
    r'\bučinkovitostima\b': 'efikasnostima',
    
    # tvrtka
    r'\btvrtka\b': 'firma',
    r'\btvrtke\b': 'firme',
    r'\btvrtki\b': 'firmi',
    r'\btvrtku\b': 'firmu',
    r'\btvrtkom\b': 'firmom',
    r'\btvrtkama\b': 'firmama',
    
    # sučelje
    r'\bsučelje\b': 'interfejs',
    r'\bsučelju\b': 'interfejsu',
    r'\bsučeljem\b': 'interfejsom',
    r'\bsučeljima\b': 'interfejsima',
    r'\bsučelja\b': 'interfejsa',
    r'\bkorisnička sučelja\b': 'korisnički interfejsi',
    r'\bkorisničkih sučelja\b': 'korisničkih interfejsa',
    
    # zaslon
    r'\bzaslon\b': 'ekran',
    r'\bzaslona\b': 'ekrana',
    r'\bzaslonu\b': 'ekranu',
    r'\bzaslonom\b': 'ekranom',
    r'\bzasloni\b': 'ekrani',
    r'\bzaslonima\b': 'ekranima',
    r'\bzaslone\b': 'ekrane',
    
    # tipkovnica
    r'\btipkovnica\b': 'tastatura',
    r'\btipkovnice\b': 'tastature',
    r'\btipkovnici\b': 'tastaturi',
    r'\btipkovnicu\b': 'tastaturu',
    r'\btipkovnicom\b': 'tastaturom',
    r'\btipkovnicama\b': 'tastaturama',
    
    # poveznica
    r'\bpoveznica\b': 'link',
    r'\bpoveznicu\b': 'link',
    r'\bpoveznice\b': 'linkovi',
    r'\bpoveznici\b': 'linku',
    r'\bpoveznicom\b': 'linkom',
    r'\bpoveznicama\b': 'linkovima',
    
    # tisuća
    r'\btisuća\b': 'hiljada',
    r'\btisuću\b': 'hiljadu',
    r'\btisuće\b': 'hiljade',
    r'\btisućom\b': 'hiljadom',
    r'\btisućama\b': 'hiljadama',
    
    # meseci
    r'\bsiječanj\b': 'januar',
    r'\bsiječnja\b': 'januara',
    r'\bsiječnju\b': 'januaru',
    r'\bveljača\b': 'februar',
    r'\bveljače\b': 'februara',
    r'\bveljači\b': 'februaru',
    r'\božujak\b': 'mart',
    r'\božujka\b': 'marta',
    r'\božujku\b': 'martu',
    r'\btravanj\b': 'april',
    r'\btravnja\b': 'aprila',
    r'\btravnju\b': 'aprilu',
    r'\bsvibanj\b': 'maj',
    r'\bsvibnja\b': 'maja',
    r'\bsvibnju\b': 'maju',
    r'\blipanj\b': 'jun',
    r'\blipnja\b': 'juna',
    r'\blipnju\b': 'junu',
    r'\bsrpanj\b': 'jul',
    r'\bsrpnja\b': 'jula',
    r'\bsrpnju\b': 'julu',
    r'\bkolovoz\b': 'avgust',
    r'\bkolovoza\b': 'avgusta',
    r'\bkolovozu\b': 'avgustu',
    r'\brujan\b': 'septembar',
    r'\brujna\b': 'septembra',
    r'\brujnu\b': 'septembru',
    r'\blistopad\b': 'oktobar',
    r'\blistopada\b': 'oktobra',
    r'\blistopadu\b': 'oktobru',
    r'\bstudeni\b': 'novembar',
    r'\bstudenog\b': 'novembra',
    r'\bstudenom\b': 'novembru',
    r'\bprosinac\b': 'decembar',
    r'\bprosinca\b': 'decembra',
    r'\bprosincu\b': 'decembru',
    
    # rješenje
    r'\brješenje\b': 'rešenje',
    r'\brješenja\b': 'rešenja',
    r'\brješenju\b': 'rešenju',
    r'\brješenjem\b': 'rešenjem',
    r'\brješenjima\b': 'rešenjima',
    
    # vještački
    r'\bvještački\b': 'veštački',
    r'\bvještačka\b': 'veštačka',
    r'\bvještačko\b': 'veštačko',
    r'\bvještačke\b': 'veštačke',
    r'\bvještačkih\b': 'veštačkih',
    
    # vidio / vidjeti
    r'\bvidio\b': 'video',
    r'\bvidjela\b': 'videla',
    r'\bvidjeli\b': 'videli',
    
    # smije / smijati se
    r'\bsmije se\b': 'smeje se',
    r'\bsmije\b': 'sme',
    r'\bsmiju se\b': 'smeju se',
    r'\bsmiju\b': 'smeju',
    r'\bsmijao se\b': 'smejao se',
    r'\bsmijao\b': 'smejao',
    r'\bsmijala se\b': 'smejala se',
    r'\bsmijala\b': 'smejala',
    r'\bsmijali se\b': 'smejali se',
    r'\bsmijali\b': 'smejali',
    r'\bsmijanje\b': 'smejanje',
    r'\bsmijati se\b': 'smejati se',
    r'\bsmijati\b': 'smejati',
    
    # dolje
    r'\bdolje\b': 'dole',
    r'\bgdje\b': 'gde',
    r'\bnijesu\b': 'nisu',
    r'\busmjeruju\b': 'usmeravaju',
    r'\buvijek\b': 'uvek',
    
    # polovica
    r'\bpolovicu\b': 'polovinu',
    r'\bpolovica\b': 'polovina',
    r'\bpolovice\b': 'polovine',
    r'\bpolovici\b': 'polovini',
    
    # svijet
    r'\bsvijet\b': 'svet',
    r'\bsvijeta\b': 'sveta',
    r'\bsvijetu\b': 'svetu',
    r'\bsvijetom\b': 'svetom',
    r'\bsvjetovi\b': 'svetovi',
    r'\bsvjetova\b': 'svetova',
    r'\bsvjetovima\b': 'svetovima',
    
    # dijete
    r'\bdijete\b': 'dete',
    r'\bdjeteta\b': 'deteta',
    r'\bdjetetu\b': 'detetu',
    r'\bdjetetom\b': 'detetom',
    r'\bdjeca\b': 'deca',
    r'\bdjece\b': 'dece',
    r'\bdjeci\b': 'deci',
    r'\bdjecom\b': 'decom',
    r'\bdječak\b': 'dečak',
    r'\bdječaka\b': 'dečaka',
    r'\bdječaku\b': 'dečaku',
    r'\bdječakom\b': 'dečakom',
    r'\bdječaci\b': 'dečaci',
    r'\bdječacima\b': 'dečacima',
    r'\bdjevojčica\b': 'devojčica',
    r'\bdjevojčice\b': 'devojčice',
    r'\bdjevojčici\b': 'devojčici',
    r'\bdjevojčicu\b': 'devojčicu',
    r'\bdjevojčicom\b': 'devojčicom',
    r'\bdjevojčicama\b': 'devojčicama',
    
    # tijelo
    r'\btijelo\b': 'telo',
    r'\btijela\b': 'tela',
    r'\btijelu\b': 'telu',
    r'\btijelom\b': 'telom',
    r'\btijelima\b': 'telima',
    
    # vrijeme
    r'\bvrijeme\b': 'vreme',
    r'\bumjesto\b': 'umesto',
    r'\bmjesto\b': 'mesto',
    r'\bmjesta\b': 'mesta',
    
    # vjerojatno
    r'\bvjerovatno\b': 'verovatno',
    r'\bvjerojatno\b': 'verovatno',
    r'\bvjerovati\b': 'verovati',
    r'\bnevjerojatno\b': 'neverovatno',
    r'\bnevjerovatno\b': 'neverovatno',
    r'\bnevjerojatan\b': 'neverovatan',
    r'\bnevjerovatan\b': 'neverovatan',
    r'\bnevjerojatna\b': 'neverovatna',
    r'\bnevjerovatna\b': 'neverovatna',
    r'\bnevjerojatne\b': 'neverovatne',
    r'\bnevjerovatne\b': 'neverovatne',
    r'\bnevjerojatnih\b': 'neverovatnih',
    r'\bnevjerovatnih\b': 'neverovatnih',
    r'\bvjerojatnost\b': 'verovatnoća',
    r'\bvjerovatnost\b': 'verovatnoća',
    r'\bvjerojatnosti\b': 'verovatnoće',
    r'\bvjerovatnosti\b': 'verovatnoće',
    
    # primjerno
    r'\bprimjerno\b': 'primereno',
    r'\bneprimjerno\b': 'neprimereno',
    r'\bprimerno\b': 'primereno',
    r'\bneprimerno\b': 'neprimereno',
    
    # vidjeti
    r'\bvidjeti\b': 'videti',
    r'\bvidjeće\b': 'videće',
    r'\bvidjećeš\b': 'videćeš',
    r'\bvidjećemo\b': 'videćemo',
    r'\bvidjećete\b': 'videćete',
    
    # donijeti
    r'\bdonijeti\b': 'doneti',
    r'\bdonijeće\b': 'doneće',
    r'\bdonijećeš\b': 'donećeš',
    r'\bdonijećemo\b': 'donećemo',
    r'\bdonijećete\b': 'donećete',
    
    # dijeliti
    r'\bdijeliti\b': 'deliti',
    r'\bdijeliće\b': 'deliće',
    r'\bdijelićeš\b': 'delićeš',
    r'\bdijelićemo\b': 'delićemo',
    r'\bdijelićete\b': 'delićete',
    
    # htjeti
    r'\bhtjeti\b': 'hteti',
    r'\bhtjeće\b': 'hteće',
    r'\bhtjećeš\b': 'htećeš',
    r'\bhtjećemo\b': 'htećemo',
    r'\bhtjećete\b': 'htećete',
    
    # riješiti
    r'\briješiti\b': 'rešiti',
    r'\briješiće\b': 'rešiće',
    r'\briješeno\b': 'rešeno',
    
    # rješavati
    r'\brješavati\b': 'rešavati',
    r'\brješava\b': 'rešava',
    r'\brješavaju\b': 'rešavaju',
    r'\brješavaš\b': 'rešavaš',
    r'\brješavamo\b': 'rešavamo',
    r'\brješavate\b': 'rešavate',
    r'\brješavao\b': 'rešavao',
    r'\brješavala\b': 'rešavala',
    r'\brješavali\b': 'rešavali',
    r'\brješavanje\b': 'rešavanje',
    r'\brješavanja\b': 'rešavanja',
    r'\brješavanju\b': 'rešavanju',
    r'\brješavanjem\b': 'rešavanjem',
    r'\brješavaću\b': 'rešavaću',
    r'\brješavaćeš\b': 'rešavaćeš',
    r'\brješavaće\b': 'rešavaće',
    r'\brješavaćemo\b': 'rešavaćemo',
    r'\brješavaćete\b': 'rešavaćete',
    
    # promijeniti
    r'\bpromijeniti\b': 'promeniti',
    r'\bpromijeni\b': 'promeni',
    r'\bpromijene\b': 'promene',
    r'\bpromijenio\b': 'promenio',
    r'\bpromijenila\b': 'promenila',
    r'\bpromijenili\b': 'promenili',
    r'\bpromijeniće\b': 'promeniće',
    r'\bpromijenjeno\b': 'promenjeno',
    r'\bpromijenivši\b': 'promenivši',
    r'\bpromijenite\b': 'promenite',
    
    # primijeniti
    r'\bprimijeniti\b': 'primeniti',
    r'\bprimijeni\b': 'primeni',
    r'\bprimijene\b': 'primene',
    r'\bprimijenio\b': 'primenio',
    r'\bprimijenila\b': 'primenila',
    r'\bprimijenili\b': 'primenili',
    r'\bprimijeniće\b': 'primeniće',
    r'\bprimijenjeno\b': 'primenjeno',
    r'\bprimijenivši\b': 'primenivši',
    r'\bprimijenite\b': 'primenite',
    
    # izravno
    r'\bizravno\b': 'direktno',
    r'\bizravan\b': 'direktan',
    r'\bizravna\b': 'direktna',
    r'\bizravne\b': 'direktne',
    r'\bizravnih\b': 'direktnih',
    r'\bizravnom\b': 'direktnom',
    r'\bizravnog\b': 'direktnog',
    r'\bizravnoga\b': 'direktnog',
    r'\bizravnu\b': 'direktnu',
    r'\bizravni\b': 'direktni',
    r'\bizravnim\b': 'direktnim',
    
    # razumjeti
    r'\brazumjeti\b': 'razumeti',
    r'\brazumjeće\b': 'razumeće',
    
    # Specifični medicinski/tehnički izrazi
    r'\bspokoen\b': 'spokojan',
    r'\bspokoena\b': 'spokojna',
    r'\bspokoeno\b': 'spokojno',
    r'\bspokoeni\b': 'spokojni',
    r'\bkomarice\b': 'komarci',
    r'\bkomarica\b': 'komarac',
    r'\bkomaricama\b': 'komarcima',
    r'\banticonceptiv\b': 'kontracepcija',
    r'\bzaštića\b': 'štiti',
    r'\boluhami\b': 'olujama',
    r'\bosvještiti\b': 'olabaviti',
    r'\bdengue šake\b': 'denga groznice',
    r'\bdengue\b': 'denga',
    r'\bfebre\b': 'groznice',
    r'\bžuta febra\b': 'žuta groznica',
    r'\bžute febre\b': 'žute groznice',
    r'\bženice\b': 'ženke',
    r'\bženicama\b': 'ženkama',
    r'\bšaljubiti\b': 'poludeti',
    r'\btrpešćine\b': 'strpljenja',
    r'\bvreže\b': 'seče',
    r'\bse smešta\b': 'maže',
    r'\bdrevne osnovice\b': 'drvene osnove',
    r'\bdrevne\b': 'drvene',
    r'\bzavari seam\b': 'zavari šav',
    r'\bseam\b': 'šav',
    r'\bukuju\b': 'bodu',
    r'\bukuje\b': 'bode',
    r'\bopakuj\b': 'obmotaj',
    r'\bopakujte\b': 'obmotajte',
    r'\bopakuje\b': 'obmotava',
    r'\bopakuju\b': 'obmotavaju',
    r'\bteško oko\b': 'čvrsto oko',
    r'\bneprimerno sigurno\b': 'nedovoljno čvrsto',
    r'\bneprimerno siguran\b': 'nedovoljno čvrst',
    r'\bneprimereno sigurno\b': 'nedovoljno čvrsto',
    r'\bneprimereno siguran\b': 'nedovoljno čvrst',
    r'\bse lako odlaze\b': 'lako olabave',
    r'\blako odlaze\b': 'lako olabave',
    r'\brezao papir\b': 'sekao papir',
    r'\brezati papir\b': 'seći papir',
    r'\bserez\b': 'isečeš',
    r'\bserežeš\b': 'isečeš',
    r'\bsereže\b': 'iseče',
    r'\bserezati\b': 'iseći',
    r'\bsrezati\b': 'iseći',
    
    # kaos / haos
    r'\bkaos\b': 'haos',
    r'\bkaosa\b': 'haosa',
    r'\bkaosu\b': 'haosu',
    r'\bkaosom\b': 'haosom',
    
    # glazba
    r'\bglazba\b': 'muzika',
    r'\bglazbe\b': 'muzike',
    r'\bglazbi\b': 'muzici',
    r'\bglazbu\b': 'muziku',
    r'\bglazbom\b': 'muzikom',
    r'\bglazbeni\b': 'muzički',
    r'\bglazbena\b': 'muzička',
    r'\bglazbeno\b': 'muzičko',
    r'\bglazbene\b': 'muzičke',
    r'\bglazbenik\b': 'muzičar',
    r'\bglazbenici\b': 'muzičari',
    
    # znanstvenik
    r'\bznanstvenik\b': 'naučnik',
    r'\bznanstvenika\b': 'naučnika',
    r'\bznanstvenici\b': 'naučnici',
    r'\bznanstvenicima\b': 'naučnicima',
    
    # povijest
    r'\bpovijest\b': 'istorija',
    r'\bpovijesti\b': 'istorije',
    r'\bpovijesni\b': 'istorijski',
    r'\bpovijesna\b': 'istorijska',
    r'\bpovijesno\b': 'istorijsko',
    r'\bpovijesne\b': 'istorijske',
    
    # sigurnosni
    r'\bsigurnosni\b': 'bezbednosni',
    r'\bsigurnosna\b': 'bezbednosna',
    r'\bsigurnosno\b': 'bezbednosno',
    r'\bsigurnosne\b': 'bezbednosne',
    r'\bsigurnosnih\b': 'bezbednosnih',
    r'\bsigurnosnom\b': 'bezbednosnom',
    r'\bsigurnosnog\b': 'bezbednog',
    
    # kemijski
    r'\bkemijski\b': 'hemijski',
    r'\bkemijska\b': 'hemijska',
    r'\bkemijsko\b': 'hemijsko',
    r'\bkemijske\b': 'hemijske',
    r'\bkemijskih\b': 'hemijskih',
    r'\bkemija\b': 'hemija',
    r'\bkemije\b': 'hemije',
    r'\bkemiji\b': 'hemiji',
    
    # prosvjed
    r'\bprosvjed\b': 'protest',
    r'\bprosvjeda\b': 'protesta',
    r'\bprosvjedu\b': 'protestu',
    r'\bprosvjedom\b': 'protestom',
    r'\bprosvjedi\b': 'protesti',
    r'\bprosvjedima\b': 'protestima',
    r'\bprosvjede\b': 'proteste',
    
    # čimbenik
    r'\bčimbenik\b': 'faktor',
    r'\bčimbenici\b': 'faktori',
    r'\bčimbenika\b': 'faktora',
    
    # nazočan
    r'\bnazočan\b': 'prisutan',
    r'\bnazočna\b': 'prisutna',
    r'\bnazočno\b': 'prisutno',
    r'\bnazočni\b': 'prisutni',
    r'\bnazočnih\b': 'prisutnih',
    r'\bnazočnost\b': 'prisustvo',
    
    # općenito - uopšte
    r'\bopćenito\b': 'uopšte',
    r'\bopćenita\b': 'uopštena',
    
    # općina
    r'\bopćina\b': 'opština',
    r'\bopćine\b': 'opštine',
    
    # osobito
    r'\bosobito\b': 'posebno',
    
    # djelovati
    r'\bdjelovati\b': 'delovati',
    r'\bdjeluje\b': 'deluje',
    r'\bdjeluju\b': 'deluju',
    r'\bdjelovao\b': 'delovao',
    r'\bdjelovala\b': 'delovala',
    r'\bdjelovali\b': 'delovali',
    r'\bdjelovanje\b': 'delovanje',
    r'\bdjelovanja\b': 'delovanja',
    r'\bdjelovanjem\b': 'delovanjem',
    
    # značajka
    r'\bznačajka\b': 'karakteristika',
    r'\bznačajke\b': 'karakteristike',
    
    # obavijest
    r'\bobavijest\b': 'obaveštenje',
    r'\bobavijesti\b': 'obaveštenja',
    
    # izvješće
    r'\bizvješće\b': 'izveštaj',
    r'\bizvješća\b': 'izveštaji',
    r'\bizvješću\b': 'izveštaju',
    
    # cijena
    r'\bcijena\b': 'cena',
    r'\bcijene\b': 'cene',
    
    # cijeli
    r'\bcijel\b': 'ceo',
    r'\bcijeli\b': 'ceo',
    r'\bcijela\b': 'cela',
    r'\bcijelo\b': 'celo',
    r'\bcijele\b': 'cele',
    r'\bcijelog\b': 'celog',
    r'\bcijelom\b': 'celom',
    r'\bcijelu\b': 'celu',
    
    # živjeti
    r'\bživjeti\b': 'živeti',
    r'\bživio\b': 'živeo',
    r'\bživjela\b': 'živela',
    r'\bživjeli\b': 'živeli',
    
    # savjet
    r'\bsavjet\b': 'savet',
    r'\bsavjeti\b': 'saveti',
    r'\bsavjeta\b': 'saveta',
    r'\bsavjetu\b': 'savetu',
    r'\bsavjetom\b': 'savetom',
    r'\bsavjetima\b': 'savetima',
    
    # dijeliti / dijeljenje
    r'\bdijeli\b': 'deli',
    r'\bdijele\b': 'dele',
    r'\bdijelio\b': 'delio',
    r'\bdijelila\b': 'delila',
    r'\bdijelili\b': 'delili',
    r'\bdijeljenje\b': 'deljenje',
    r'\bdijeljenja\b': 'deljenja',
    
    # razumjeti (oblici koji su nedostajali)
    r'\brazumio\b': 'razumeo',
    r'\brazumjela\b': 'razumela',
    r'\brazumjeli\b': 'razumeli',
    r'\brazumijem\b': 'razumem',
    r'\brazumiješ\b': 'razumeš',
    r'\brazumije\b': 'razume',
    r'\brazumijemo\b': 'razumemo',
    r'\brazumijete\b': 'razumete',
    r'\brazumiju\b': 'razumeju',
    
    # mijenjati / izmijeniti
    r'\bmijenjati\b': 'menjati',
    r'\bmijenja\b': 'menja',
    r'\bmijenjaju\b': 'menjaju',
    r'\bmijenjao\b': 'menjao',
    r'\bmijenjala\b': 'menjala',
    r'\bmijenjali\b': 'menjali',
    r'\bmijenjanje\b': 'menjanje',
    r'\bmijenjanja\b': 'menjanja',
    r'\bizmijeniti\b': 'izmeniti',
    r'\bizmijeni\b': 'izmeni',
    r'\bizmijene\b': 'izmene',
    r'\bizmijenio\b': 'izmenio',
    r'\bizmijenila\b': 'izmenila',
    r'\bizmijenili\b': 'izmenili',
    
    # Uopštena ijekavska pravila bez potrebe za celim rečima
    r'osjeć': 'oseć',
    r'osmijeh': 'osmeh',
    r'osmijesi': 'osmesi',
    r'smijeh': 'smeh',
    r'smijesi': 'smesi',
    r'smiješ': 'smeš',
    r'riječ': 'reč',
    r'rješ': 'reš',
    r'riješ': 'reš',
    r'procjen': 'procen',
    r'procijen': 'procen',
    r'ocjen': 'ocen',
    r'ocijen': 'ocen',
    r'izmjene': 'izmene',
    r'izmjen': 'izmen',
    r'izmijen': 'izmen',
    r'promjen': 'promen',
    r'promijen': 'promen',
    r'primjen': 'primen',
    r'primijen': 'primen',
    r'dijel': 'del',
    r'vrijem': 'vrem',
    r'živje': 'žive',
    r'vidje': 'vide',
    r'razumje': 'razume',
    r'spriječ': 'spreč',
    r'donije': 'done',
    r'htje': 'hte',
    r'\bdonio\b': 'doneo',
    r'\bhtio\b': 'hteo',
    r'slijed': 'sled',
    r'sljed': 'sled',
    r'slijedi': 'sledi',
    r'vijek': 'vek',
    r'vjek': 'vek',
    r'vječ': 'več',
    r'procjena': 'procena',
    r'ocjena': 'ocena',
    r'izmjena': 'izmena',
    r'promjena': 'promena',
    r'primjena': 'primena',
    r'mjera': 'mera',
    r'mjere': 'mere',
    r'mjeru': 'meru',
    r'mjerom': 'merom',
    r'mjerama': 'merama',
    r'mjeriti': 'meriti',
    r'mjerilo': 'merilo',
    r'vjera': 'vera',
    r'vjere': 'vere',
    r'vjeru': 'veru',
    r'smjer': 'smer',
    r'brijeg': 'breg',
    r'tijek': 'tok'
}

TO_LATIN_REPLACEMENTS = [
    (re.compile(pat, re.IGNORECASE), repl)
    for pat, repl in LATIN_REPLACEMENTS_RAW.items()
]

def to_latin(text: str) -> str:
    if not text:
        return text
    res = []
    for char in text:
        res.append(CYRILLIC_TO_LATIN.get(char, char))
    text = "".join(res)
    
    # Dodatno čišćenje bugarskih/čeških specifičnih karaktera
    text = text.replace('ť', 't')
    text = text.replace('Ť', 'T')
    text = text.replace('ъ', 'a')
    text = text.replace('Ъ', 'A')
    
    for pattern_compiled, repl in TO_LATIN_REPLACEMENTS:
        text = pattern_compiled.sub(lambda m, r=repl: preserve_case(m, r), text)
        
    return text
