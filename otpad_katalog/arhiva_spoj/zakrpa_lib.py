"""Zajednička logika zakrpa: ciljana zamjena sidrenih nizova (ne prepisuje datoteku), .bak, py_compile, hashevi, rollback."""
import hashlib
import py_compile
import shutil
import time


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def primijeni(put: str, zamjene: list, oznaka: str, suho: bool = False) -> int:
    """zamjene = [(ime, sidro, novo)]. Svako sidro mora postojati TOČNO jednom. oznaka = niz koji dokazuje da je već primijenjeno."""
    original = open(put, "rb").read()
    tekst = original.decode("utf-8")
    if oznaka in tekst:
        print(f"VEĆ PRIMIJENJENO (nađen {oznaka}), ništa ne radim")
        return 0
    for ime, sidro, _novo in zamjene:
        n = tekst.count(sidro)
        if n != 1:
            print(f"STOP: {ime} nađen {n} puta (treba točno 1). Datoteka se razlikuje od pročitane; ništa nije mijenjano.")
            return 1
    novo_tekst = tekst
    for _ime, sidro, novo in zamjene:
        novo_tekst = novo_tekst.replace(sidro, novo, 1)
    print("sha256 prije :", sha(original))
    print("sha256 poslije:", sha(novo_tekst.encode("utf-8")))
    if suho:
        print("SUHO: ništa nije upisano")
        return 0
    bak = f"{put}.bak.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    shutil.copy2(put, bak)
    open(put, "w", encoding="utf-8").write(novo_tekst)
    try:
        py_compile.compile(put, doraise=True)
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, put)
        print(f"py_compile pao, vraćeno iz {bak}: {e}")
        return 1
    print(f"OK. rollback: cp -p {bak} {put}  (pa restart servisa)")
    return 0
