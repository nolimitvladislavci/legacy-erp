"""
Nonprofit accounting setup — poziva se kad se registrira udruga/zadruga/ustanova.
Sadrzi FINA-kompatibilnu analitiku za automatsko generiranje PR-RAS-NPF obrasca.

Svaki konto ima komentar s pripadajucim AOP brojem iz PR-RAS-NPF obrasca.
"""
from konto.models import KontoAccount
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

NONPROFIT_CHART = [
    # Klasa 0 — Nefinancijska imovina
    ("0", "Nefinancijska imovina", "asset"),
    ("01", "Neproizvedena dugotrajna imovina", "asset"),
    ("011", "Materijalna imovina - prirodna bogatstva", "asset"),
    ("012", "Nematerijalna imovina (patenti, licence)", "asset"),
    ("019", "Ispravak vrijednosti neproizvedene imovine", "asset"),
    ("02", "Proizvedena dugotrajna imovina", "asset"),
    ("021", "Gradjevinski objekti", "asset"),
    ("022", "Postrojenja i oprema", "asset"),
    ("023", "Prijevozna sredstva", "asset"),
    ("029", "Ispravak vrijednosti proizvedene imovine", "asset"),
    ("04", "Sitni inventar", "asset"),
    ("05", "Nefinancijska imovina u pripremi", "asset"),
    ("06", "Proizvedena kratkotrajna imovina", "asset"),

    # Klasa 1 — Financijska imovina (analiticki)
    ("1", "Financijska imovina", "asset"),
    ("11", "Novac u banci i blagajni", "asset"),
    ("111", "Novac na ziro racunu", "asset"),
    ("112", "Novac u blagajni", "asset"),
    ("12", "Depoziti i jamcevni polozi", "asset"),
    ("13", "Potrazivanja za prihode", "asset"),
    ("131", "Potrazivanja za clanarine", "asset"),
    ("132", "Potrazivanja za donacije", "asset"),
    ("133", "Potrazivanja od prodaje", "asset"),
    ("16", "Potrazivanja za vise placene poreze", "asset"),
    ("19", "Rashodi buducih razdoblja", "asset"),

    # Klasa 2 — Obveze
    ("2", "Obveze", "liability"),
    ("21", "Obveze za rashode", "liability"),
    ("211", "Obveze za place", "liability"),
    ("212", "Obveze za materijalne rashode", "liability"),
    ("23", "Obveze za kredite i zajmove", "liability"),
    ("24", "Odgodeno placanje rashoda", "liability"),
    ("25", "Obveze za PDV i ostale poreze", "liability"),

    # Klasa 3 — Prihodi (mapirano na PR-RAS-NPF AOP pozicije)
    ("3", "Prihodi", "income"),
    ("31", "Prihodi od prodaje roba i pruzanja usluga", "income"),       # AOP 002
    ("3111", "Prihodi od prodaje roba", "income"),                       # AOP 003
    ("3112", "Prihodi od pruzanja usluga", "income"),                    # AOP 004
    ("32", "Prihodi od clanarina i clanskih doprinosa", "income"),       # AOP 005
    ("3211", "Clanarine", "income"),                                      # AOP 006
    ("3212", "Clanski doprinosi", "income"),                              # AOP 007
    ("33", "Prihodi po posebnim propisima", "income"),                   # AOP 008
    ("3311", "Prihodi po posebnim propisima iz proracuna", "income"),    # AOP 009
    ("3312", "Prihodi po posebnim propisima iz ostalih izvora", "income"),# AOP 010
    ("34", "Prihodi od imovine", "income"),                              # AOP 011
    ("341", "Prihodi od financijske imovine", "income"),                 # AOP 012
    ("3411", "Prihodi od kamata za dane zajmove", "income"),             # AOP 013
    ("3412", "Prihodi od kamata po vrijednosnim papirima", "income"),    # AOP 014
    ("3413", "Kamate na orocena sredstva i depozite", "income"),         # AOP 015
    ("3414", "Prihodi od zateznih kamata", "income"),                    # AOP 016
    ("3415", "Prihodi od pozitivnih tecajnih razlika", "income"),        # AOP 017
    ("3416", "Prihodi od dividendi", "income"),                          # AOP 018
    ("3418", "Ostali prihodi od financijske imovine", "income"),         # AOP 020
    ("342", "Prihodi od nefinancijske imovine", "income"),               # AOP 021
    ("3421", "Prihodi od zakupa i iznajmljivanja", "income"),            # AOP 022
    ("3422", "Ostali prihodi od nefinancijske imovine", "income"),       # AOP 023
    ("35", "Prihodi od donacija", "income"),                             # AOP 024
    ("351", "Prihodi od donacija iz proracuna", "income"),               # AOP 025
    ("3511", "Donacije iz drzavnog proracuna", "income"),                # AOP 026
    ("3512", "Donacije iz proracuna JLP(R)S", "income"),                 # AOP 027
    ("352", "Prihodi od inozemnih vlada i medunarodnih org", "income"),  # AOP 028
    ("353", "Prihodi od pravnih osoba", "income"),                       # AOP 029
    ("354", "Prihodi od gradana i kucanstava", "income"),                # AOP 030
    ("355", "Ostali prihodi od donacija", "income"),                     # AOP 031
    ("36", "Ostali prihodi", "income"),                                  # AOP 032
    ("361", "Prihodi od naknade stete i refundacija", "income"),         # AOP 033
    ("3611", "Prihodi od naknade steta", "income"),                      # AOP 034
    ("3612", "Prihodi od refundacija", "income"),                        # AOP 035
    ("362", "Prihodi od prodaje dugotrajne imovine", "income"),          # AOP 036
    ("363", "Ostali nespomenuti prihodi", "income"),                     # AOP 037
    ("3631", "Otpis obveza", "income"),                                  # AOP 038
    ("3632", "Naplacena otpisana potrazivanja", "income"),               # AOP 039
    ("3633", "Ostali nespomenuti prihodi", "income"),                    # AOP 040
    ("37", "Prihodi od povezanih NPF organizacija", "income"),          # AOP 041
    ("3711", "Tekuci prihodi od povezanih NPF org", "income"),           # AOP 042
    ("3712", "Kapitalni prihodi od povezanih NPF org", "income"),        # AOP 043

    # Klasa 4 — Rashodi (mapirano na PR-RAS-NPF AOP pozicije)
    ("4", "Rashodi", "expense"),                                         # AOP 044
    ("41", "Rashodi za radnike", "expense"),                             # AOP 045
    ("411", "Place (bruto)", "expense"),                                 # AOP 046
    ("4111", "Place za redovan rad", "expense"),                         # AOP 047
    ("4112", "Place u naravi", "expense"),                               # AOP 048
    ("4113", "Place za prekovremeni rad", "expense"),                    # AOP 049
    ("4114", "Place za posebne uvjete rada", "expense"),                 # AOP 050
    ("412", "Ostali rashodi za radnike", "expense"),                     # AOP 051
    ("413", "Doprinosi na place", "expense"),                            # AOP 052
    ("4131", "Doprinosi za zdravstveno osiguranje", "expense"),          # AOP 053
    ("4132", "Doprinosi za zaposljavanje", "expense"),                   # AOP 054
    ("4133", "Doprinosi za mirovinsko (poslodavac)", "expense"),         # AOP 055
    ("4134", "Posebni doprinos za zaposljavanje OSI", "expense"),        # AOP 056
    ("42", "Materijalni rashodi", "expense"),                            # AOP 057
    ("421", "Naknade troskova radnicima", "expense"),                    # AOP 058
    ("4211", "Sluzbena putovanja", "expense"),                           # AOP 059
    ("4212", "Naknade za prijevoz i rad na terenu", "expense"),          # AOP 060
    ("4213", "Strucno usavrsavanje radnika", "expense"),                 # AOP 061
    ("422", "Naknade clanovima u tijelima", "expense"),                  # AOP 062
    ("4221", "Naknade za obavljanje aktivnosti", "expense"),             # AOP 063
    ("4222", "Naknade troskova sluzbenih putovanja", "expense"),         # AOP 064
    ("4223", "Naknade ostalih troskova", "expense"),                     # AOP 065
    ("4224", "Ostale naknade", "expense"),                               # AOP 066
    ("423", "Naknade volonterima", "expense"),                           # AOP 067
    ("424", "Naknade ostalim osobama izvan radnog odnosa", "expense"),   # AOP 072
    ("425", "Rashodi za usluge", "expense"),                             # AOP 077
    ("4251", "Usluge telefona, poste i prijevoza", "expense"),           # AOP 078
    ("4252", "Usluge tekuceg i investicijskog odrzavanja", "expense"),   # AOP 079
    ("4253", "Usluge promidzbe i informiranja", "expense"),              # AOP 080
    ("4254", "Komunalne usluge", "expense"),                             # AOP 081
    ("4255", "Zakupnine i najamnine", "expense"),                        # AOP 082
    ("4256", "Zdravstvene i veterinarske usluge", "expense"),            # AOP 083
    ("4257", "Intelektualne i osobne usluge", "expense"),                # AOP 084
    ("4258", "Racunalne usluge", "expense"),                             # AOP 085
    ("4259", "Ostale usluge", "expense"),                                # AOP 086
    ("426", "Rashodi za materijal i energiju", "expense"),               # AOP 087
    ("4261", "Uredski materijal i ostali mat. rashodi", "expense"),      # AOP 088
    ("4262", "Materijal i sirovine", "expense"),                         # AOP 089
    ("4263", "Energija", "expense"),                                     # AOP 090
    ("4264", "Sitan inventar i auto gume", "expense"),                   # AOP 091
    ("429", "Ostali nespomenuti materijalni rashodi", "expense"),        # AOP 092
    ("4291", "Premije osiguranja", "expense"),                           # AOP 093
    ("4292", "Reprezentacija", "expense"),                                # AOP 094
    ("4293", "Clanarine (rashod)", "expense"),                           # AOP 095
    ("4294", "Kotizacije", "expense"),                                   # AOP 096
    ("4295", "Ostali nespomenuti materijalni rashodi", "expense"),       # AOP 097
    ("43", "Rashodi amortizacije", "expense"),                           # AOP 098
    ("44", "Financijski rashodi", "expense"),                            # AOP 099
    ("441", "Kamate za izdane vrijednosne papire", "expense"),           # AOP 100
    ("442", "Kamate za primljene kredite i zajmove", "expense"),         # AOP 101
    ("4421", "Kamate za primljene kredite banaka", "expense"),           # AOP 102
    ("4422", "Kamate za primljene robne zajmove", "expense"),            # AOP 103
    ("443", "Ostali financijski rashodi", "expense"),                    # AOP 105
    ("4431", "Bankarske usluge i usluge platnog prometa", "expense"),    # AOP 106
    ("4432", "Negativne tecajne razlike", "expense"),                    # AOP 107
    ("4433", "Zatezne kamate", "expense"),                               # AOP 108
    ("4434", "Ostali nespomenuti financijski rashodi", "expense"),       # AOP 109
    ("45", "Donacije dane", "expense"),                                  # AOP 110
    ("451", "Tekuce donacije", "expense"),                               # AOP 111
    ("4511", "Tekuce donacije", "expense"),                              # AOP 112
    ("4512", "Stipendije", "expense"),                                   # AOP 113
    ("452", "Kapitalne donacije", "expense"),                            # AOP 114
    ("46", "Ostali rashodi", "expense"),                                 # AOP 115
    ("461", "Kazne, penali i naknade stete", "expense"),                 # AOP 116
    ("462", "Ostali nespomenuti rashodi", "expense"),                    # AOP 121
    ("47", "Rashodi vezani uz financ. povezanih NPF org", "expense"),   # AOP 126

    # Klasa 5 — Vlastiti izvori
    ("5", "Vlastiti izvori", "equity"),
    ("51", "Vlastiti izvori", "equity"),
    ("52", "Visak/manjak prihoda", "equity"),
    ("5221", "Visak prihoda - preneseni", "equity"),                     # AOP 136
    ("5222", "Manjak prihoda - preneseni", "equity"),                    # AOP 137
]


def setup_nonprofit_accounts(company, force=False):
    """Kreira neprofitni kontni plan za udrugu. Preskace ako vec postoji."""
    if not force and KontoAccount.objects.filter(company=company).exists():
        return False

    created = []
    for code, name, acc_type in NONPROFIT_CHART:
        obj, is_new = KontoAccount.objects.get_or_create(
            company=company, code=code,
            defaults={"name": name, "account_type": acc_type, "is_active": True},
        )
        if is_new:
            created.append(code)
    return created
