"""The set of portals the app searches, and how their results are combined.

Con ``only_portal`` il registro cerca su un portale solo: e' la scelta che l'utente fa
all'avvio. Riaprire una voce salvata resta libero da quella scelta, perche' un episodio
vive dove e' stato trovato.

Two rules the aggregation follows:

* **A failing portal must not break the search.** If one site is down or has changed
  domain, results from the others still come through — that is most of the value of
  having more than one.
* **Order is preserved per source.** Results are interleaved so the first page shows
  something from each portal instead of everything from the fastest one.
"""

from __future__ import annotations

import re

from ..canonical import canonical_key
from ..net import PAGE_SIZE, AnimeSaturnClient
from .animesaturn import AnimeSaturnSource
from .animeunity import AnimeUnitySource
from .base import AnimeSource


class SourcesUnavailable(Exception):
    """Nessun portale attivo ha risposto.

    Non e' la stessa cosa di «nessun risultato»: la' la domanda e' stata posta e la
    risposta era vuota, qui non si e' potuto nemmeno chiedere. Tenerli distinti e'
    cio' che permette all'interfaccia di parlare di connessione invece di scrivere
    «Nessun risultato», e alla cura del dominio di partire -- finche' questo caso
    tornava una lista vuota, quella cura non scattava mai.

    Gemella di ``SourcesUnavailableException`` dell'app Android.
    """

    def __init__(self, errors: dict[str, str]) -> None:
        #: Un messaggio per portale, con il suo identificativo.
        self.errors = dict(errors)
        super().__init__(
            "Nessun portale raggiungibile.\n"
            + "\n".join(f"{k}: {v}" for k, v in list(self.errors.items())[:3])
        )


class SourceRegistry:
    """The portals in use, in priority order."""

    def __init__(
        self,
        client: AnimeSaturnClient | None = None,
        animeunity_base_url: str | None = None,
        only_portal: str | None = None,
    ) -> None:
        # In ordine di preferenza: il primo che ha l'episodio viene usato per riprodurlo.
        self._sources: list[AnimeSource] = [
            AnimeSaturnSource(client),
            AnimeUnitySource(base_url=animeunity_base_url),
        ]
        #: Il portale scelto dall'utente, o ``None`` per cercarli tutti.
        #:
        #: Vale per catalogo, ricerca e suggerimenti. NON vale per riaprire una voce
        #: salvata: un preferito o una puntata in «continua a guardare» vivono sul
        #: portale da cui vennero, e da li' devono riaprirsi, qualunque sia il portale
        #: scelto adesso. Che l'elenco mostri un portale alla volta e' una scelta di
        #: vista, presa altrove (``gui/portal_filter.py``); qui, aperta una voce, si va
        #: dove sta.
        self.only_portal = only_portal

    def set_animeunity_base_url(self, base_url: str) -> None:
        """Point AnimeUnity at another domain without restarting the app.

        The portal moves; when the published list or the user says it has, the
        source is rebuilt in place so the next search already uses the new
        address.
        """
        for index, source in enumerate(self._sources):
            if source.id == AnimeUnitySource.id:
                self._sources[index] = AnimeUnitySource(base_url=base_url)
                return

    # ------------------------------------------------------------------ #
    @property
    def sources(self) -> list[AnimeSource]:
        return list(self._sources)

    def known_portal(self, portal: str | None) -> str | None:
        """``portal`` se questa versione lo conosce, altrimenti ``None``.

        Serve a far concordare le due meta' dell'app su un identificativo salvato che
        non corrisponde a nessun portale: una preferenza scritta da una versione che
        ne offriva un altro, un file delle impostazioni toccato a mano, un portale
        ritirato. ``_browse`` qui sotto ripiega su **tutti** i portali; il filtro degli
        elenchi (``portal_filter``) non trova niente e li **svuota**. Il risultato era
        un catalogo che funziona accanto a preferiti e cronologia vuoti, con
        l'intestazione che scrive «Tutti i portali»: all'utente si legge come dati
        perduti, che e' la lettura peggiore possibile per un filtro.

        Si normalizza qui, al confine, e non dentro il filtro: quella e' una funzione
        pura, il suo comportamento su un identificativo ignoto e' definito e fissato
        dai vettori condivisi con l'app Android. Il difetto non era la regola, era che
        nessuno validava cio' che le veniva passato.

        Fra le due direzioni possibili si prende la sicura: mostrare tutto. Nascondere
        tutto non e' mai la risposta giusta a «non so cosa sia questo».
        """
        if portal is None:
            return None
        return portal if any(s.id == portal for s in self._sources) else None

    def all_quality_options(self) -> dict[str, str]:
        """Le qualita' che l'app puo' offrire **in assoluto**, portale attivo o meno.

        Serve a costruire il comando una volta sola. :meth:`quality_options` dice invece
        cosa si puo' scegliere *adesso*, e decide se quel comando va acceso: sono due
        domande diverse, e confonderle lascerebbe una tendina vuota appena si apre l'app
        sul portale che non offre scelte.
        """
        unite: dict[str, str] = {}
        for source in self._sources:
            unite.update(source.quality_options())
        return unite

    def quality_options(self) -> dict[str, str]:
        """Le qualita' offerte da almeno uno dei portali attivi.

        Vuoto quando nessuno ne offre: allora non c'e' niente da scegliere, e il comando
        va spento dicendo perche'. Con piu' portali attivi si uniscono, perche' basta che
        uno sappia onorarla -- la stessa regola degli avvisi sui filtri, e per la stessa
        ragione: una possibilita' che esiste da qualche parte non va negata a monte.
        """
        unite: dict[str, str] = {}
        for source in self._browse:
            unite.update(source.quality_options())
        return unite

    def expressible_filters(self) -> dict[str, set[str] | None]:
        """I filtri esprimibili da ALMENO uno dei portali attivi.

        Stessa regola degli avvisi: se uno sa rispondere la domanda e' ponibile, e un
        elenco vuoto vuol dire davvero «nessun risultato». Quindi una dimensione resta
        limitata solo se la limitano **tutti**, e i valori buoni sono l'**unione** dei
        loro. Con tutti i portali attivi non si limita quasi niente, ed e' giusto:
        scegliendone uno solo, il suo silenzio diventa visibile -- ed e' esattamente la
        situazione in cui questo serve.
        """
        attivi = self._browse
        if not attivi:
            return {}
        comuni: dict[str, set[str] | None] = {
            chiave: (None if valori is None else set(valori))
            for chiave, valori in attivi[0].expressible_filters().items()
        }
        for source in attivi[1:]:
            suoi = source.expressible_filters()
            for chiave in list(comuni):
                if chiave not in suoi:
                    # Questo portale non limita la dimensione: non e' limitata.
                    del comuni[chiave]
                    continue
                miei, altri = comuni[chiave], suoi[chiave]
                unione = (set() if miei is None else set(miei)) | (
                    set() if altri is None else set(altri)
                )
                comuni[chiave] = unione or None
        return comuni

    @property
    def _browse(self) -> list[AnimeSource]:
        """I portali su cui cercare: quello scelto, o tutti se non si e' scelto.

        Se l'identificativo scelto non corrisponde a nessun portale — una preferenza
        vecchia, un portale rimosso — si torna a cercarli tutti invece di non cercare da
        nessuna parte: un elenco vuoto per sempre sarebbe il modo peggiore di reagire a
        una stringa che non si riconosce.
        """
        if self.only_portal is None:
            return self._sources
        scelti = [s for s in self._sources if s.id == self.only_portal]
        return scelti or self._sources

    @property
    def browsing(self) -> list[AnimeSource]:
        """I portali davvero interrogati, per poterli nominare all'utente.

        Serve agli avvisi: con un portale solo attivo, accusare del silenzio il portale
        che non e' stato nemmeno provato manderebbe l'utente a cercare il dominio
        sbagliato.
        """
        return list(self._browse)

    def add(self, source: AnimeSource) -> None:
        self._sources.append(source)

    def get(self, source_id: str) -> AnimeSource | None:
        """The source a record came from, or the first one when unspecified.

        Falling back matters for entries saved before sources existed: they carry no id,
        and they all came from the portal that was then the only one.
        """
        if not source_id:
            return self._sources[0] if self._sources else None
        for source in self._sources:
            if source.id == source_id:
                return source
        return self._sources[0] if self._sources else None

    @property
    def primary(self) -> AnimeSource:
        return self._sources[0]

    # ------------------------------------------------------------------ #
    def search(
        self,
        title: str | None = None,
        *,
        sort: str = "standard",
        page: int = 1,
        dub: str = "",
        filters: dict | None = None,
        on_source_error=None,
        meta: dict | None = None,
    ) -> list[dict]:
        """Search every portal and return the combined records.

        A portal that raises is skipped rather than allowed to empty the whole result.

        ``on_source_error(source_id, message)`` viene chiamata per ogni portale che non
        ha risposto, **anche quando gli altri hanno funzionato**: serve a chi chiama per
        curare in sottofondo un dominio cambiato. Senza questa notizia, un portale che
        aveva traslocato restava assente in silenzio finche' non cadevano anche gli
        altri.

        ``meta``, se passato, riceve ``page_full``: se **almeno un** portale attivo ha
        consegnato una pagina piena. Chi chiama non puo' ricavarlo dalla lista che torna,
        e provarci e' costato quasi tutto il catalogo di AnimeSaturn: la fusione dei
        duplicati accorcia la pagina di proposito -- un anime doppiato e il suo gemello
        sottotitolato sono lo stesso anime, e ne resta una scheda sola -- quindi 30 schede
        del sito diventavano 26, il confronto con la pagina del sito falliva e
        l'interfaccia concludeva «finito». Oltre la prima pagina non si andava.

        Si misura **prima** di fondere, perche' e' allora che il numero significa «quante
        me ne ha date il portale» invece di «quante ne restano da mostrare».

        Se hanno ceduto **tutti** quelli attivi si solleva :class:`SourcesUnavailable`
        invece di restituire una lista vuota: quel vuoto verrebbe mostrato come «nessun
        risultato», cioe' come risposta a una domanda che non e' stata posta. Il
        confronto e' contro i portali ATTIVI, non contro tutti: scegliendone uno solo,
        il suo fallimento non raggiungerebbe mai il totale, e si tornerebbe a mentire
        proprio nel caso per cui questo controllo esiste.
        """
        attivi = self._browse
        per_source: list[list[dict]] = []
        errors: dict[str, str] = {}
        for source in attivi:
            try:
                per_source.append(
                    source.search(title, sort=sort, page=page, dub=dub, filters=filters)
                )
            except Exception as exc:  # noqa: BLE001 - one broken portal must not sink the rest
                per_source.append([])
                errors[source.id] = f"{type(exc).__name__}: {exc}"
                if on_source_error is not None:
                    on_source_error(source.id, str(exc))
        if attivi and len(errors) == len(attivi):
            raise SourcesUnavailable(errors)
        if meta is not None:
            meta["page_full"] = any(len(l) >= PAGE_SIZE for l in per_source)
        return _dedupe(_interleave(per_source))

    def suggest(self, query: str) -> list[dict]:
        per_source: list[list[dict]] = []
        for source in self._browse:
            try:
                per_source.append(source.suggest(query))
            except Exception:  # noqa: BLE001
                per_source.append([])
        return _interleave(per_source)

    def fetch_anime_detail(self, slug: str, source_id: str = "") -> dict:
        source = self.get(source_id)
        return source.fetch_anime_detail(slug) if source else {}

    def fetch_anime_detail_for(self, anime) -> dict:
        """Episodes for an anime, asked of the portal that listed it.

        A portal can carry the listing and no episodes at all -- a season announced
        but not yet released, most often the dubbed edition. Until now that left the
        page simply empty, even when the other portal had the episodes. Playback has
        had this fallback for a while; the anime page had not.

        The dubbed flag is carried across deliberately. The canonical key drops the
        language marker on purpose, so "X" and "X (ITA)" look identical to it: without
        this guard a dubbed page would quietly fill with subtitled episodes.
        """
        detail = self.fetch_anime_detail(anime.slug, getattr(anime, "source_id", ""))
        if detail.get("episodes"):
            return detail

        wanted = canonical_key(getattr(anime, "title", "") or "")
        if not wanted:
            return detail
        dubbed = bool(getattr(anime, "dubbed", False))
        origin = getattr(anime, "source_id", "")
        for source in self._sources:
            if source.id == origin:
                continue
            try:
                for record in source.search(anime.title):
                    if bool(record.get("dubbed")) != dubbed:
                        continue
                    if wanted not in _all_keys(record):
                        continue
                    other = source.fetch_anime_detail(record.get("slug", ""))
                    if other.get("episodes"):
                        return other
            except Exception:  # noqa: BLE001 - a failing portal must not empty the page
                continue
        return detail

    def resolve_download_url(
        self, watch_path: str, source_id: str = "", quality: str = ""
    ) -> str:
        source = self.get(source_id)
        if source is None:
            raise RuntimeError("Nessuna sorgente disponibile.")
        return source.resolve_download_url(watch_path, quality)

    def resolve_with_fallback(
        self,
        watch_path: str,
        source_id: str,
        title: str,
        episode_number: str,
        quality: str = "",
    ) -> tuple[str, str]:
        """Play an episode, trying the other portals if its own cannot serve it.

        Returns ``(media_url, source_id_used)``.

        This is the payoff of having more than one source. Until now a portal that had
        changed domain, gone down, or simply lacked that episode left the user stuck. Now
        the app looks the anime up on the other portals by its canonical title, finds the
        matching episode number and plays that instead — without asking anything.
        """
        errors: list[str] = []
        preferred = self.get(source_id)
        if preferred is not None:
            try:
                return (
                    preferred.resolve_download_url(watch_path, quality),
                    preferred.id,
                )
            except Exception as exc:  # noqa: BLE001 - that is what the fallback is for
                errors.append(f"{preferred.label}: {exc}")

        wanted = canonical_key(title)
        for source in self._sources:
            if preferred is not None and source.id == preferred.id:
                continue
            try:
                # Si confronta con ogni nome che l'altro portale conosce, non col solo
                # titolo mostrato: è la stessa ragione per cui i doppioni si fondono, e
                # senza di essa il ripiego fallirebbe proprio quando i due siti chiamano
                # l'anime in lingue diverse.
                matches = [
                    record
                    for record in source.search(title)
                    if wanted in _all_keys(record)
                ]
                for record in matches[:2]:  # a couple of candidates is plenty
                    detail = source.fetch_anime_detail(record.get("slug", ""))
                    for episode in detail.get("episodes", []):
                        if str(episode.get("number")) == str(episode_number):
                            # La preferenza segue anche nel ripiego: ripescare
                            # l'episodio su un altro portale non e' una ragione per
                            # ignorare la qualita' chiesta.
                            url = source.resolve_download_url(
                                episode.get("watch_path", ""), quality
                            )
                            if url:
                                return url, source.id
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source.label}: {exc}")

        detail = "\n".join(errors[:3])
        raise RuntimeError(
            f"Nessun portale è riuscito a fornire questo episodio.\n{detail}"
        )

    def close(self) -> None:
        for source in self._sources:
            try:
                source.close()
            except Exception:  # noqa: BLE001 - closing must never raise on shutdown
                pass


def _all_keys(record: dict) -> set[str]:
    """Ogni chiave con cui un risultato è riconoscibile: titolo mostrato e alternativi."""
    names = [record.get("title") or ""] + list(record.get("aliases") or [])
    keys = {canonical_key(n) for n in names if n}
    keys.discard("")
    return keys


def _interleave(groups: list[list[dict]]) -> list[dict]:
    """Round-robin the groups, so no single portal fills the first page on its own."""
    merged: list[dict] = []
    for i in range(max((len(g) for g in groups), default=0)):
        for group in groups:
            if i < len(group):
                merged.append(group[i])
    return merged


def _dedupe(records: list[dict]) -> list[dict]:
    """Collapse the same anime listed by several portals into one result.

    Matching is done on every name a record is known by, not just the one shown. Portals
    disagree on language — one lists "Yona of the Dawn", the other "Akatsuki no Yona" —
    and those texts share nothing, so comparing display titles alone would show the anime
    twice, with two separate resume points.

    The first occurrence wins the card (sources are in preference order), gains any field
    the other filled in, and keeps the list of portals that have it. That list is what
    makes the fallback possible when one portal cannot play an episode.
    """
    merged: dict[int, dict] = {}
    key_to_group: dict[str, int] = {}
    order: list[int] = []

    for record in records:
        keys = _all_keys(record)
        if not keys:
            keys = {record.get("slug") or ""}

        # Among the groups this record could join, take the first that does not
        # disagree with it about the season.
        candidates = []
        for k in keys:
            g = key_to_group.get(k)
            if g is not None and g not in candidates:
                candidates.append(g)
        group = next(
            (g for g in candidates if not _season_conflict(keys, merged[g]["_keys"])),
            None,
        )
        entry = {
            "source_id": record.get("source_id", ""),
            "source_label": record.get("source_label", ""),
            "slug": record.get("slug", ""),
            "episodes_count": record.get("episodes_count") or 0,
        }

        if group is None:
            group = len(merged)
            winner = dict(record)
            winner["_keys"] = set(keys)
            winner["sources"] = [entry]
            merged[group] = winner
            order.append(group)
        else:
            winner = merged[group]
            winner["_keys"].update(keys)
            if all(s["source_id"] != entry["source_id"] for s in winner["sources"]):
                winner["sources"].append(entry)
            # Fill in whatever the winning portal left empty: a poster or plot from the
            # other one is better than none.
            for field in ("poster", "plot", "year", "score", "type"):
                if not winner.get(field) and record.get(field):
                    winner[field] = record[field]
            if not winner.get("episodes_count") and record.get("episodes_count"):
                winner["episodes_count"] = record["episodes_count"]

        # Every name this record is known by now points at the group, so a later record
        # sharing any one of them lands here too.
        for k in keys:
            key_to_group.setdefault(k, group)

    result = []
    for g in order:
        winner = merged[g]
        winner.pop("_keys", None)
        result.append(winner)
    return result


# A trailing number is the season: "…loveiswar" against "…loveiswar2".
_TRAILING_NUMBER = re.compile(r"^(.*?)([0-9]+)$")


def _season_conflict(keys_a: set[str], keys_b: set[str]) -> bool:
    """True when two sets of names describe the same work in *different* seasons.

    Portals sometimes distinguish seasons by punctuation alone — one franchise separates
    them with ":" and "?" — and punctuation is deliberately dropped from the key, so those
    two names collapse into one. Without this check the second season would be absorbed
    into the first through that shared name and play the wrong episodes.

    The season number decides it, because it is the one part of a title never discarded:
    if the same base name appears with two different numbers, these are two works.
    """
    seasons_a: dict[str, set[str]] = {}
    for key in keys_a:
        m = _TRAILING_NUMBER.match(key)
        base, season = (m.group(1), m.group(2)) if m else (key, "")
        seasons_a.setdefault(base, set()).add(season)
    for key in keys_b:
        m = _TRAILING_NUMBER.match(key)
        base, season = (m.group(1), m.group(2)) if m else (key, "")
        if base in seasons_a and season not in seasons_a[base]:
            return True
    return False
