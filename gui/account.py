"""Account dialog: sign up / sign in, and the state of cross-device sync.

Deliberately small: one email, one password, one button. The password is never stored —
only the refresh token Firebase returns, which "Esci" deletes.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .cloud import DEFAULT_SENDER, CloudClient, CloudError


#: Il consiglio sullo spam, scritto una volta sola.
#:
#: Le email di Firebase partono da un indirizzo ``firebaseapp.com``: un dominio che non e'
#: nostro e senza storia d'invio, quindi i filtri lo trattano con sospetto. Cambiarlo
#: richiederebbe un dominio proprio nel campo «Da», e non ce n'e' uno — percio' l'unica
#: mitigazione vera e' quella che puo' fare chi riceve, e va detta.
#:
#: Non si scrive l'indirizzo esatto del mittente perche' non e' verificato: mandare a
#: cercare nello spam una stringa sbagliata e' peggio che darne una generica. «
#: firebaseapp.com» invece e' certo, e basta a trovarla.
#:
#: Compare in tre messaggi diversi: tre copie a mano diventerebbero tre consigli diversi
#: al primo ritocco.
_SPAM = (
    "Quasi sempre finisce nella POSTA INDESIDERATA, e il mittente è\n"
    f"      {DEFAULT_SENDER}\n"
    "Cercalo lì, apri il link, e segnala il messaggio come «non spam»: "
    "le prossime arriveranno nella posta in arrivo."
)


class AccountDialog(QDialog):
    """Sign in or create an account, then sync history and favourites."""

    signed_in = Signal()
    signed_out = Signal()
    sync_requested = Signal()

    def __init__(self, client: CloudClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Account · Sincronizzazione")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        intro = QLabel(
            "Accedi per ritrovare cronologia e preferiti su PC e telefono.\n"
            "Se non hai un account, scrivi email e password e crealo."
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("La tua email")
        layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password (almeno 6 caratteri)")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._sign_in)
        layout.addWidget(self.password_input)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        self.verify_note = QLabel("")
        self.verify_note.setObjectName("Muted")
        self.verify_note.setWordWrap(True)
        self.verify_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.verify_note.setVisible(False)
        layout.addWidget(self.verify_note)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.signup_button = QPushButton("Crea account")
        self.signup_button.setObjectName("Ghost")
        self.signup_button.clicked.connect(self._sign_up)
        buttons.addWidget(self.signup_button)

        self.signin_button = QPushButton("Accedi")
        self.signin_button.setObjectName("Primary")
        self.signin_button.clicked.connect(self._sign_in)
        buttons.addWidget(self.signin_button)

        self.forgot_button = QPushButton("Password dimenticata?")
        self.forgot_button.setObjectName("Ghost")
        self.forgot_button.clicked.connect(self._reset_password)
        buttons.addWidget(self.forgot_button)

        self.verify_button = QPushButton("Rimanda email di verifica")
        self.verify_button.setObjectName("Ghost")
        self.verify_button.clicked.connect(self._resend_verification)
        buttons.addWidget(self.verify_button)

        self.signout_button = QPushButton("Esci")
        self.signout_button.setObjectName("Danger")
        self.signout_button.clicked.connect(self._sign_out)
        buttons.addWidget(self.signout_button)

        self.sync_button = QPushButton("Sincronizza ora")
        self.sync_button.setObjectName("Primary")
        self.sync_button.clicked.connect(self._sync_now)
        buttons.addWidget(self.sync_button)
        layout.addLayout(buttons)

        close = QPushButton("Chiudi")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

        self._check_verification()
        self._refresh_state()

    # ------------------------------------------------------------------ #
    def _check_verification(self) -> None:
        """Rilegge dal server se l'indirizzo e' stato confermato.

        Solo quando risulta non confermato: una conferma non si annulla, quindi saputa
        una volta non va richiesta piu', e si evita una chiamata di rete a ogni apertura.

        E' il momento giusto per chiederlo: si apre questa finestra proprio dopo aver
        cliccato il link nella posta, e un avviso che restasse in piedi dopo aver fatto
        la cosa giusta insegnerebbe a ignorarlo.
        """
        config = self.client.config
        if not config.signed_in or config.email_verified:
            return
        try:
            self.client.refresh_email_verified()
        except CloudError:
            pass  # senza rete l'avviso resta: e' la supposizione prudente

    def _refresh_state(self) -> None:
        """Show either the sign-in form or the signed-in summary, never both."""
        config = self.client.config
        signed_in = config.signed_in
        for widget in (self.email_input, self.password_input):
            widget.setVisible(not signed_in)
        self.signup_button.setVisible(not signed_in)
        self.signin_button.setVisible(not signed_in)
        self.forgot_button.setVisible(not signed_in)
        self.signout_button.setVisible(signed_in)
        self.sync_button.setVisible(signed_in)
        self.verify_button.setVisible(signed_in and not config.email_verified)
        if not signed_in and not self.email_input.text().strip():
            # Il promemoria: uscendo, l'email era l'unico indizio su quale account si
            # avesse, e veniva cancellata proprio in quel momento. Non e' una
            # credenziale, e da sola non apre niente.
            self.email_input.setText(config.last_email)
        if signed_in and not config.email_verified:
            # Dire che l'email è già partita, e dove cercarla, non è un dettaglio: senza
            # quella frase il primo gesto è premere «Rimanda», cioè chiederne una seconda
            # pochi secondi dopo la prima, e Firebase blocca con «troppi tentativi».
            problema = self.client.verification_error
            if problema:
                self.verify_note.setText(
                    f"⚠  Non ho potuto mandare l'email di verifica: {problema}\n"
                    "Riprova fra qualche minuto con «Rimanda email di verifica». "
                    "Finché l'indirizzo non è confermato non potrai reimpostare la "
                    "password se la dimentichi."
                )
            else:
                self.verify_note.setText(
                    f"⚠  Email di verifica inviata a {config.email} — aprila e "
                    f"torna qui.\n\n{_SPAM}\n\n"
                    "La sincronizzazione funziona già. Ma finché non confermi non "
                    "potrai reimpostare la password se la dimentichi: il link "
                    "arriverebbe a un indirizzo che forse non è il tuo."
                )
        self.verify_note.setVisible(signed_in and not config.email_verified)
        if signed_in:
            when = config.last_sync
            detail = (
                f"Ultima sincronizzazione: {time.strftime('%d/%m alle %H:%M', time.localtime(when))}"
                if when
                else "Non hai ancora sincronizzato."
            )
            self.status.setText(f"Collegato come {config.email}.\n{detail}")
        else:
            self.status.setText("")

    def _busy(self, message: str) -> None:
        self.status.setText(message)
        self.setEnabled(False)
        self.repaint()

    def _done(self) -> None:
        self.setEnabled(True)

    # ------------------------------------------------------------------ #
    def _credentials(self) -> tuple[str, str] | None:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or "@" not in email:
            self.status.setText("Inserisci un indirizzo email valido.")
            return None
        if len(password) < 6:
            self.status.setText("La password deve avere almeno 6 caratteri.")
            return None
        return email, password

    def _sign_up(self) -> None:
        creds = self._credentials()
        if not creds:
            return
        self._busy("Creazione account…")
        try:
            self.client.sign_up(*creds)
        except CloudError as exc:
            self._done()
            self.status.setText(str(exc))
            return
        self._after_auth()

    def _sign_in(self) -> None:
        creds = self._credentials()
        if not creds:
            return
        self._busy("Accesso…")
        try:
            self.client.sign_in(*creds)
        except CloudError as exc:
            self._done()
            self.status.setText(str(exc))
            return
        self._after_auth()

    def _after_auth(self) -> None:
        self._done()
        self.password_input.clear()  # never keep the password around
        self._refresh_state()
        self.signed_in.emit()
        self.sync_requested.emit()  # first sync merges this device into the account

    def _reset_password(self) -> None:
        """Manda il link per reimpostare la password all'indirizzo scritto.

        Non passa da ``_credentials``: chiedere la password a chi l'ha dimenticata non
        avrebbe senso, e qui serve il solo indirizzo.
        """
        email = self.email_input.text().strip()
        if not email or "@" not in email:
            self.status.setText("Scrivi l'indirizzo email del tuo account.")
            return
        self._busy("Invio del link…")
        try:
            self.client.send_password_reset(email)
        except CloudError as exc:
            self._done()
            self.status.setText(str(exc))
            return
        self._done()
        # Non si scrive «inviata». Firebase accetta in silenzio anche un indirizzo che
        # non esiste, per non rivelare a chiunque chi e' registrato: promettere l'arrivo
        # sarebbe una bugia proprio verso chi ha sbagliato a scrivere l'indirizzo, cioe'
        # verso l'unico che da quel messaggio ha qualcosa da capire.
        self.status.setText(
            f"Se esiste un account con {email}, riceverai un'email col link per "
            f"reimpostare la password.\n{_SPAM}"
        )

    def _resend_verification(self) -> None:
        """Rimanda l'email di verifica, se serve ancora."""
        self._busy("Controllo…")
        try:
            # Prima si guarda: il link puo' essere stato cliccato nel frattempo, e
            # mandarne un'altra sarebbe posta inutile a chi ha gia' fatto la sua parte.
            if self.client.refresh_email_verified():
                self._done()
                self._refresh_state()
                self.status.setText("L'indirizzo è già confermato.")
                return
            self.client.send_email_verification()
        except CloudError as exc:
            self._done()
            # Qualunque sia il motivo, il consiglio utile è lo stesso: una email può
            # essere già in viaggio da quando hai creato l'account.
            self.status.setText(
                f"{exc}\nSe hai appena creato l'account, un'email di verifica è già "
                "partita allora: cercala anche nella posta indesiderata prima di "
                "chiederne un'altra."
            )
            return
        self._done()
        self._refresh_state()
        self.status.setText(
            f"Email di verifica inviata a {self.client.config.email}.\n{_SPAM}\n"
            "Poi riapri questa finestra."
        )

    def _sign_out(self) -> None:
        self.client.sign_out()
        self._refresh_state()
        self.signed_out.emit()

    def _sync_now(self) -> None:
        self.status.setText("Sincronizzazione in corso…")
        self.sync_requested.emit()

    def report(self, message: str) -> None:
        """Called back by the main window when a sync round finishes."""
        self.status.setText(message)
        self._refresh_state() if self.client.config.signed_in else None
