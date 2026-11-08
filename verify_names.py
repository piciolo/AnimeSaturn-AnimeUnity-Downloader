# -*- coding: utf-8 -*-
"""Cerca i nomi che il codice legge e che non esistono da nessuna parte nel file.

Nasce da un difetto uscito fino all'utente: ``recent()`` ordinava con ``_to_float``
senza averlo importato, quindi solleva un ``NameError`` a ogni chiamata e la scheda
«Continua» restava vuota per sempre. Nessuna voce era andata perduta -- l'elenco non
veniva mai costruito.

Python si accorge di un nome inesistente solo quando ci passa sopra, e una finestra
avviata con ``pythonw`` non ha una console dove la traccia possa comparire: l'app
continuava a funzionare con un elenco morto e senza dire niente. E' il modo peggiore in
cui un difetto possa presentarsi, quindi serve una macchina che lo cerchi.

Approssimazione voluta: si raccolgono tutti i nomi legati in QUALUNQUE punto del file
(modulo, argomenti, assegnazioni, cicli, ``with``, ``except``, comprensioni, import) e si
segnala ogni lettura di un nome che non sia fra quelli ne' un builtin. Gli ambiti non
vengono distinti, quindi un nome definito in una funzione e letto in un'altra non viene
riportato: in cambio non ci sono falsi allarmi, e un nome che nel file non esiste affatto
non puo' passare -- che e' esattamente il caso da prendere.

Uso: python verify_names.py
"""

from __future__ import annotations

import ast
import builtins
import io
import pathlib
import sys

RADICE = pathlib.Path(__file__).resolve().parent

#: Nomi che esistono sempre, senza che il file li definisca.
NOTI = set(dir(builtins)) | {
    "__file__",
    "__name__",
    "__doc__",
    "__package__",
    "__spec__",
    "__builtins__",
    "__loader__",
    "__annotations__",
    "__debug__",
    "__path__",
}


def nomi_legati(albero: ast.AST) -> set[str]:
    """Ogni nome che questo file lega, in qualunque ambito."""
    fuori: set[str] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, (ast.Store, ast.Del)):
            fuori.add(nodo.id)
        elif isinstance(
            nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            fuori.add(nodo.name)
        elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                fuori.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(nodo, ast.arg):
            fuori.add(nodo.arg)
        elif isinstance(nodo, ast.ExceptHandler) and nodo.name:
            fuori.add(nodo.name)
        elif isinstance(nodo, (ast.Global, ast.Nonlocal)):
            fuori.update(nodo.names)
        elif isinstance(nodo, ast.withitem) and isinstance(
            nodo.optional_vars, ast.Name
        ):
            fuori.add(nodo.optional_vars.id)
    return fuori


def main() -> int:
    guai = 0
    file = sorted(RADICE.glob("gui/**/*.py")) + sorted(RADICE.glob("*.py"))
    for percorso in file:
        testo = io.open(percorso, encoding="utf-8").read()
        try:
            albero = ast.parse(testo, filename=str(percorso))
        except SyntaxError as exc:
            print(f"SINTASSI  {percorso.name}: {exc}")
            guai += 1
            continue
        disponibili = nomi_legati(albero) | NOTI
        visti: dict[str, int] = {}
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load):
                if nodo.id not in disponibili:
                    visti.setdefault(nodo.id, nodo.lineno)
        for nome, riga in sorted(visti.items(), key=lambda kv: kv[1]):
            dove = percorso.relative_to(RADICE).as_posix()
            print(f"MAI DEFINITO  {dove}:{riga}  ->  {nome}")
            guai += 1

    print()
    if guai:
        print(f"{guai} da guardare")
        return 1
    print(f"nessun nome fantasma in {len(file)} file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
