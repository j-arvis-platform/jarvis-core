"""
Email SMTP wrapper pour J-ARVIS V2.

V1 rule carried over: respect client inbox.
Max 1 email par client par 24h — a implementer via table Supabase
`rate_limit_email` quand disponible (cf ticket post go-live).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Iterable

import aiosmtplib

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


@dataclass
class EmailClient:
    """Wrapper async aiosmtplib pour l'envoi transactionnel Gmail/OVH/etc."""

    host: str
    port: int
    user: str
    password: str
    from_name: str
    from_email: str
    timeout: float = DEFAULT_TIMEOUT

    @property
    def from_header(self) -> str:
        return formataddr((self.from_name, self.from_email))

    def _build_message(self, to: str | Iterable[str], subject: str,
                       body_html: str, body_text: str | None = None,
                       cc: Iterable[str] | None = None,
                       bcc: Iterable[str] | None = None,
                       attachments: Iterable[str | Path] | None = None,
                       ) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self.from_header
        msg["To"] = to if isinstance(to, str) else ", ".join(to)
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid(domain=self.from_email.split("@", 1)[-1])
        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        if body_text is None:
            body_text = "Votre client mail ne supporte pas le HTML."
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")

        for att in attachments or []:
            path = Path(att)
            if not path.is_file():
                raise FileNotFoundError(f"piece jointe introuvable : {path}")
            data = path.read_bytes()
            msg.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=path.name,
            )
        return msg

    async def send_email(self, to: str | Iterable[str], subject: str,
                         body_html: str, body_text: str | None = None,
                         cc: Iterable[str] | None = None,
                         bcc: Iterable[str] | None = None,
                         attachments: Iterable[str | Path] | None = None,
                         ) -> dict:
        """Envoie un email. Retourne {message_id, recipients}.

        Ne log JAMAIS le password. En cas d'erreur SMTP, l'exception
        aiosmtplib remonte — c'est au caller de decider de la politique.
        """
        msg = self._build_message(
            to=to, subject=subject, body_html=body_html, body_text=body_text,
            cc=cc, bcc=bcc, attachments=attachments,
        )

        recipients: list[str] = []
        recipients.extend([to] if isinstance(to, str) else list(to))
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        logger.info(
            "smtp_send host=%s from=%s to=%s subject=%r",
            self.host, self.from_email, recipients, subject,
        )

        await aiosmtplib.send(
            msg,
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            start_tls=True,
            timeout=self.timeout,
        )
        return {"message_id": msg["Message-ID"], "recipients": recipients}

    async def send_email_with_template(self, to: str | Iterable[str],
                                       template_name: str,
                                       variables: dict | None = None,
                                       subject: str | None = None,
                                       **kwargs) -> dict:
        """Rend un template HTML (templates/email/<name>.html) et l'envoie.

        Le rendu utilise `str.format_map` — champs referencees comme
        {prenom} dans le template, sans logique conditionnelle.
        Pour du templating riche, passer a Jinja2 plus tard.
        """
        templates_dir = Path(__file__).resolve().parents[2] / "templates" / "email"
        path = templates_dir / f"{template_name}.html"
        if not path.is_file():
            raise FileNotFoundError(f"template introuvable : {path}")

        raw = path.read_text(encoding="utf-8")
        rendered = raw.format_map(_SafeDict(variables or {}))

        final_subject = subject or (variables or {}).get("subject") or template_name
        return await self.send_email(
            to=to, subject=final_subject, body_html=rendered, **kwargs
        )


class _SafeDict(dict):
    """Dict qui renvoie '{cle}' pour les cles manquantes (format_map)."""

    def __missing__(self, key):  # type: ignore[override]
        return "{" + key + "}"


def build_from_env(env: dict[str, str] | None = None) -> EmailClient:
    import os
    env = env or os.environ
    return EmailClient(
        host=env["SMTP_HOST"],
        port=int(env.get("SMTP_PORT", "587")),
        user=env["SMTP_USER"],
        password=env["SMTP_PASSWORD"],
        from_name=env.get("SMTP_FROM_NAME", "J-ARVIS"),
        from_email=env.get("SMTP_FROM_EMAIL", env["SMTP_USER"]),
    )
