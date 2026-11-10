"""Reusable custom widgets: anime cards, episode list and download rows."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from .models import Anime
from .net import AnimeSaturnClient
from .theme import ACCENT, ACCENT_HOVER
from .workers import PosterWorker

class EpisodeList(QListWidget):
    """La lista degli episodi, con un ▶ cliccabile su ogni riga.

    Gemella della riga episodio dell'app Android, che è una spunta per i download con un
    tasto play di fianco. Qui la spunta resta quella di Qt e il play è **disegnato**, non
    un widget per riga: un anime lungo ha più di mille episodi, e mille pulsanti veri si
    pagherebbero in attesa e in memoria a ogni apertura della scheda. Disegnarlo non
    costa niente e si comporta come un pulsante, perché il clic in quella colonna non
    arriva alla spunta — chi vuole guardare un episodio non sta scegliendo cosa scaricare.
    """

    #: L'episodio di cui si è premuto il play.
    play_requested = Signal(object)

    #: Larghezza della colonna del play. Larga abbastanza da prenderci dentro senza
    #: mirare, che è il minimo per qualcosa che si clicca mille volte.
    COLUMN = 38

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hovered = -1
        self._pressed = -1
        # Serve a sapere quando il puntatore entra nella colonna: senza, il ▶ resterebbe
        # spento e si leggerebbe come una decorazione invece che come un comando.
        self.setMouseTracking(True)
        self.setItemDelegate(_PlayColumn(self))

    # ------------------------------------------------------------------ #
    def play_rect(self, row: QRect) -> QRect:
        """La parte della riga ``row`` occupata dal play."""
        return QRect(
            row.right() - self.COLUMN + 1, row.top(), self.COLUMN, row.height()
        )

    def hovered_row(self) -> int:
        """La riga il cui play è sotto il puntatore, o ``-1``."""
        return self._hovered

    def _play_row_at(self, point) -> int:
        """L'indice della riga il cui play sta sotto ``point``, o ``-1``."""
        item = self.itemAt(point)
        if item is None:
            return -1
        if not self.play_rect(self.visualItemRect(item)).contains(point):
            return -1
        return self.row(item)

    # ------------------------------------------------------------------ #
    def mouseMoveEvent(self, event) -> None:
        row = self._play_row_at(event.position().toPoint())
        if row != self._hovered:
            self._hovered = row
            self.viewport().update()
            if row >= 0:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hovered != -1:
            self._hovered = -1
            self.viewport().update()
        self.unsetCursor()
        super().leaveEvent(event)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        """Scorrendo, la riga sotto il puntatore cambia senza che il puntatore si muova."""
        super().scrollContentsBy(dx, dy)
        self._refresh_hover()

    def _refresh_hover(self) -> None:
        """Ricalcola quale play sta sotto il puntatore, senza eventi di movimento.

        ``_hovered`` e' un **indice di riga**, e sotto un puntatore fermo lo
        scorrimento cambia la riga che gli sta sotto senza produrre un solo evento di
        movimento: una rotella, una trascinata della barra, le frecce. Il ▶ restava
        illuminato e ingrandito su una riga mentre il clic -- che la riga la ricalcola
        -- ne riproduceva un'altra. Un comando che indica un episodio e ne esegue un
        altro e' peggio di un comando che non si vede.

        La barra di scorrimento e' un figlio della lista, non del suo viewport: passandoci
        sopra non arriva alcun ``leaveEvent``, ed e' un altro modo di restare illuminati
        a torto. Qui si ricalcola comunque, e un punto fuori dal viewport non trova
        righe.
        """
        if self.underMouse():
            riga = self._play_row_at(self.viewport().mapFromGlobal(QCursor.pos()))
        else:
            riga = -1
        if riga == self._hovered:
            return
        self._hovered = riga
        self.viewport().update()
        if riga >= 0:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event) -> None:
        row = self._play_row_at(event.position().toPoint())
        if row >= 0 and event.button() == Qt.LeftButton:
            self._pressed = row
            episode = self.item(row).data(Qt.UserRole)
            if episode is not None:
                self.play_requested.emit(episode)
            return  # non passa oltre: la spunta non si muove
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Il rilascio sul play si ingoia come la pressione.

        Non è simmetria per eleganza: lasciandolo passare, la lista vedrebbe un rilascio
        senza la pressione che lo precede, e Qt usa proprio quella coppia per decidere se
        muovere la spunta. Il risultato era che il primo clic su una casella **dopo** un
        play non faceva niente, e l'utente lo avrebbe scoperto accorgendosi che i
        download non partivano.
        """
        if self._pressed >= 0:
            self._pressed = -1
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        """Invio guarda l'episodio della riga corrente.

        Il pulsante «Anteprima» era l'unico modo di guardare un episodio senza mouse, e
        ritirarlo in favore di un ▶ disegnato ha lasciato questa lista raggiungibile
        dalla tastiera e inservibile: le frecce muovono la riga corrente, lo spazio ne
        muove la spunta, e non restava niente che riproducesse.

        Si gestisce il tasto invece di collegare il segnale ``activated`` di Qt, che
        pure arriva: su Windows quel segnale lo emette anche il **doppio clic**, che su
        questa lista e' gia' la vecchia scorciatoia per guardare, e si aprirebbero due
        finestre sullo stesso episodio -- lo stesso difetto che
        ``mouseDoubleClickEvent`` qui sotto esiste per evitare.

        Che la riga corrente si muova anche senza ``ItemIsSelectable`` e' stato
        misurato, non dedotto. E si guarda la riga su cui si e', non la prima: era
        proprio l'errore del vecchio pulsante.
        """
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            episode = item.data(Qt.UserRole) if item is not None else None
            if episode is not None:
                self.play_requested.emit(episode)
                return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Due clic rapidi sul play aprono un player, non due.

        Il secondo clic arriva come doppio clic, che altrove su questa lista è la vecchia
        scorciatoia per guardare l'episodio: sul play quella scorciatoia farebbe partire
        una seconda finestra sullo stesso episodio.
        """
        row = self._play_row_at(event.position().toPoint())
        if row >= 0:
            self._pressed = row  # così anche il rilascio che segue resta qui
            return
        super().mouseDoubleClickEvent(event)


class _PlayColumn(QStyledItemDelegate):
    """Disegna il ▶ di :class:`EpisodeList`, e tiene il testo lontano da lui."""

    def __init__(self, view: EpisodeList) -> None:
        super().__init__(view)
        self._view = view

    def sizeHint(self, option, index) -> QSize:
        # Un po' più alta del necessario: la riga è anche un bersaglio da cliccare, e
        # alla distanza di una riga di testo si sbaglia episodio.
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), hint.height() + 8)

    def paint(self, painter, option, index) -> None:
        # Il rettangolo del testo si restringe, il glifo non si sposta: su una riga lunga
        # («⏸ incompleto — riprendi») le due cose finirebbero una sopra l'altra.
        testo = QStyleOptionViewItem(option)
        testo.rect = QRect(option.rect)
        testo.rect.setRight(option.rect.right() - self._view.COLUMN)
        super().paint(painter, testo, index)

        acceso = self._view.hovered_row() == index.row()
        painter.save()
        painter.setPen(QColor(ACCENT_HOVER if acceso else ACCENT))
        font = painter.font()
        font.setPointSizeF(font.pointSizeF() + (2.0 if acceso else 0.5))
        painter.setFont(font)
        painter.drawText(self._view.play_rect(option.rect), Qt.AlignCenter, "▶")
        painter.restore()



class MultiSelectDropdown(QPushButton):
    """A dropdown button that opens a checkbox list for multi-value selection.

    Mirrors the site's own filter controls: no selection means "all"; the button label
    summarises the current choice. Long option lists (genres, years) scroll inside the
    popup. ``values()`` returns the checked option values.
    """

    changed = Signal()

    def __init__(self, placeholder: str, options: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FilterSelect")
        self.setCursor(Qt.PointingHandCursor)
        self._placeholder = placeholder
        self._checks: dict[str, QCheckBox] = {}

        menu = QMenu(self)
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(8, 8, 8, 8)
        box.setSpacing(3)
        for label, value in options.items():
            if not value:  # the "Tutti"/"Ogni…" entry is implicit (no selection = all)
                continue
            check = QCheckBox(label)
            check.toggled.connect(self._on_toggle)
            box.addWidget(check)
            self._checks[value] = check

        # Long lists scroll inside the popup instead of making a giant menu.
        if len(self._checks) > 12:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setMinimumWidth(230)
            scroll.setMaximumHeight(320)
            scroll.setWidget(container)
            host: QWidget = scroll
        else:
            host = container

        action = QWidgetAction(menu)
        action.setDefaultWidget(host)
        menu.addAction(action)
        self.setMenu(menu)
        self._sync_text()

    def _on_toggle(self, _checked: bool) -> None:
        self._sync_text()
        self.changed.emit()

    def _sync_text(self) -> None:
        labels = [c.text() for c in self._checks.values() if c.isChecked()]
        if not labels:
            self.setText(f"{self._placeholder}:  tutti")
        elif len(labels) <= 2:
            self.setText(f"{self._placeholder}:  " + ", ".join(labels))
        else:
            self.setText(f"{self._placeholder}:  {len(labels)} selezionati")

    def values(self) -> list[str]:
        """Return the checked option values (empty list = no constraint)."""
        return [value for value, check in self._checks.items() if check.isChecked()]

    def clear(self) -> None:
        """Uncheck every option."""
        for check in self._checks.values():
            check.blockSignals(True)
            check.setChecked(False)
            check.blockSignals(False)
        self._sync_text()

    def restrict(self, consentiti: set[str] | None, motivo: str = "") -> list[str]:
        """Spegne le voci che il portale attivo non sa esprimere.

        ``consentiti`` a ``None`` vuol dire che l'intera dimensione qui non esiste, e il
        comando si spegne tutto; un insieme spegne le voci che non vi compaiono. Le voci
        spente portano ``motivo`` come suggerimento: una voce grigia senza spiegazione e'
        un pezzo di app che sembra rotto, e non si capisce che tornerebbe scegliendo
        l'altro portale.

        Le voci spente vengono anche **deselezionate**, e i loro valori restituiti. Non
        basta spegnere il comando: il vincolo vive nello stato della ricerca, e
        resterebbe ad agire da invisibile. Un filtro che morde senza piu' un comando che
        lo mostri e' peggio di un filtro che non c'e'.

        Si toglie valore per valore, non la dimensione intera: con Azione e Magia
        scelti, buttare via il genere **allargherebbe** la ricerca invece di
        restringerla, ed e' il contrario di quel che hai chiesto.
        """
        tolti: list[str] = []
        for valore, check in self._checks.items():
            buono = consentiti is not None and valore in consentiti
            if not buono and check.isChecked():
                check.blockSignals(True)
                check.setChecked(False)
                check.blockSignals(False)
                tolti.append(valore)
            check.setEnabled(buono)
            check.setToolTip("" if buono else motivo)
        spenta = not any(c.isEnabled() for c in self._checks.values())
        self.setEnabled(not spenta)
        self.setToolTip(motivo if spenta else "")
        if spenta:
            self.setText(f"{self._placeholder}:  non disponibile")
        else:
            self._sync_text()
        return tolti

    def unrestrict(self) -> None:
        """Riaccende tutte le voci: il portale attivo le sa esprimere tutte."""
        for check in self._checks.values():
            check.setEnabled(True)
            check.setToolTip("")
        self.setEnabled(True)
        self.setToolTip("")
        self._sync_text()

POSTER_W = 176
POSTER_H = 248
# Card must be wider than the poster by its left+right margins (8 + 8), otherwise the
# fixed-size poster overflows the content area and paints over the hover border.
CARD_WIDTH = POSTER_W + 16
# Every inner element has a fixed height and so does the card, so all cards are
# identical and no leftover vertical space can stretch the badges/meta rows.
BADGE_H = 22
META_H = 20
TITLE_H = 38
# Fixed card height: margins + poster + title + badges + meta + a small cushion that
# the trailing stretch absorbs, so content never clips and cards stay identical.
CARD_HEIGHT = 8 + POSTER_H + 8 + TITLE_H + 8 + BADGE_H + 8 + META_H + 10 + 12  # = 382


def human_size(num_bytes: float) -> str:
    """Return a human-readable size string."""
    if num_bytes < 0:
        return "?"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < step:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"


def _badge(text: str, object_name: str = "Badge") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignCenter)
    label.setFixedHeight(BADGE_H)
    return label


class AnimeCard(QFrame):
    """A clickable poster card representing one anime."""

    # Shared in-memory pixmap cache (posters rarely change and repeat across tabs).
    _pixmap_cache: dict[str, QPixmap] = {}

    clicked = Signal(object)  # emits the Anime

    def __init__(self, anime: Anime, client: AnimeSaturnClient, pool) -> None:
        super().__init__()
        self.anime = anime
        self._client = client
        self._pool = pool

        self.setObjectName("Card")
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 10)
        layout.setSpacing(8)

        self.poster = QLabel()
        self.poster.setFixedSize(POSTER_W, POSTER_H)
        self.poster.setAlignment(Qt.AlignCenter)
        self.poster.setScaledContents(False)
        self.poster.setStyleSheet(
            "background:#15161f;border-radius:10px;color:#5b6079;font-size:32px;"
        )
        self.poster.setText("🎬")
        layout.addWidget(self.poster)

        title = QLabel(anime.title)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        title.setFixedHeight(TITLE_H)
        title.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(title)

        badges = QHBoxLayout()
        badges.setSpacing(5)
        if anime.anime_type:
            badges.addWidget(_badge(anime.anime_type))
        if anime.year:
            badges.addWidget(_badge(anime.year))
        if anime.dubbed:
            badges.addWidget(_badge("DUB", "BadgeDub"))
        badges.addStretch(1)
        layout.addLayout(badges)

        meta = QLabel(f"{anime.episodes_count} ep · ⭐ {anime.score or '–'}")
        meta.setObjectName("Muted")
        meta.setFixedHeight(META_H)
        layout.addWidget(meta)
        layout.addStretch(1)  # absorb any slack at the bottom, never in the badges row

        self.setToolTip(anime.title)
        self._load_poster()

    def _load_poster(self) -> None:
        url = self.anime.poster
        if not url:
            return
        cached = self._pixmap_cache.get(url)
        if cached is not None:
            self._apply_pixmap(cached)
            return
        worker = PosterWorker(self._client, url)
        worker.signals.done.connect(self._on_poster_bytes)
        self._pool.start(worker)

    def _on_poster_bytes(self, url: str, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        self._pixmap_cache[url] = pixmap
        self._apply_pixmap(pixmap)

    def _apply_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            POSTER_W,
            POSTER_H,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self.poster.setText("")
        self.poster.setPixmap(scaled)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.anime)
        super().mousePressEvent(event)


class DownloadRow(QFrame):
    """A single row in the downloads panel, tracking one episode's progress."""

    cancel_requested = Signal(int)  # task_id
    remove_requested = Signal(int)  # task_id

    def __init__(self, task_id: int, title: str) -> None:
        super().__init__()
        self.task_id = task_id
        self._finished = False

        self.setObjectName("Row")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 12, 10)
        outer.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:600;")
        left.addWidget(self.title_label)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(10)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        bar_row.addWidget(self.bar, 1)

        self.status_label = QLabel("In coda…")
        self.status_label.setObjectName("Muted")
        self.status_label.setMinimumWidth(190)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bar_row.addWidget(self.status_label)
        left.addLayout(bar_row)

        outer.addLayout(left, 1)

        self.action_button = QPushButton("Annulla")
        self.action_button.setObjectName("Danger")
        self.action_button.setFixedWidth(88)
        self.action_button.clicked.connect(self._on_action)
        outer.addWidget(self.action_button)

    def _on_action(self) -> None:
        if self._finished:
            self.remove_requested.emit(self.task_id)
        else:
            self.cancel_requested.emit(self.task_id)
            self.status_label.setText("Annullamento…")
            self.action_button.setEnabled(False)

    def set_status(self, text: str) -> None:
        if not self._finished:
            self.status_label.setText(text)

    def set_progress(self, downloaded: int, total: int, speed: float) -> None:
        if self._finished:
            return
        if total > 0:
            percent = int(downloaded / total * 100)
            self.bar.setRange(0, 100)
            self.bar.setValue(percent)
            self.status_label.setText(
                f"{human_size(downloaded)} / {human_size(total)}  ·  "
                f"{human_size(speed)}/s"
            )
        else:
            self.bar.setRange(0, 0)  # indeterminate
            self.status_label.setText(
                f"{human_size(downloaded)}  ·  {human_size(speed)}/s"
            )

    def set_finished(self, success: bool, message: str) -> None:
        self._finished = True
        self.bar.setRange(0, 100)
        self.action_button.setEnabled(True)
        self.action_button.setObjectName("Ghost")
        self.action_button.setText("Rimuovi")
        self.action_button.style().unpolish(self.action_button)
        self.action_button.style().polish(self.action_button)

        if success:
            self.bar.setValue(100)
            # ``startswith`` e non uguaglianza: il messaggio puo' portare il motivo
            # («il 1080p non esiste per questo episodio, c'è il 720p»), e quel motivo
            # e' la ragione per cui il messaggio esiste. Resta un esito riuscito, non
            # un errore: il file c'e'.
            if message.startswith("Già presente"):
                self.status_label.setText(f"✓ {message}")
                self.status_label.setToolTip(message)
            else:
                self.status_label.setText("✓ Completato")
            self.status_label.setStyleSheet("color:#3ecf8e;")
        elif message == "Annullato":
            self.status_label.setText("Annullato")
            self.status_label.setStyleSheet("color:#9aa0b4;")
        else:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color:#ff5c72;")
            self.status_label.setToolTip(message)
