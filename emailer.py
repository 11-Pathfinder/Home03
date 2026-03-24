"""Email digest sender via Gmail SMTP."""

from __future__ import annotations

import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Template

from models import Property

TEMPLATE_PATH = Path("templates/digest.html")


def render_digest(properties: list[Property]) -> str:
    """Render the HTML email digest."""
    template = Template(TEMPLATE_PATH.read_text())
    return template.render(
        properties=properties,
        date=date.today().strftime("%d %B %Y"),
    )


def send_digest(properties: list[Property], email_config: dict) -> None:
    """Send HTML digest email via Gmail SMTP."""
    html = render_digest(properties)

    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        # Save to file as fallback when no email configured
        out = Path("data/digest.html")
        out.write_text(html)
        print(f"No GMAIL_APP_PASSWORD set. Saved digest to {out}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Property Finder: {len(properties)} new listings — {date.today().strftime('%d %b %Y')}"
    msg["From"] = email_config["from"]
    msg["To"] = email_config["to"]

    # Plain text fallback
    plain = "\n\n".join(
        f"{p.address} — £{p.price:,} — {p.bedrooms or '?'} bed\n{p.url}"
        for p in properties
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_config["from"], password)
        server.send_message(msg)
