"""Pydantic-Modelle (Request/Response).

Warum Decimal statt float? Geldbeträge müssen exakt sein. Pydantic v2
serialisiert Decimal im JSON als String ("1234.50") -> das Frontend
parst bewusst selbst (z. B. mit decimal.js oder Number() zur Anzeige).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

# Wiederverwendbare, an die DB-Constraints angelehnte Typen
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Hours = Annotated[Decimal, Field(gt=0, le=24, max_digits=4, decimal_places=2)]
HourlyRate = Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]

Ampel = Literal["green", "yellow", "red"]


class ProjectStatus(str, Enum):
    geplant = "geplant"
    aktiv = "aktiv"
    abgeschlossen = "abgeschlossen"
    archiviert = "archiviert"


# ----------------------------- Projekte -------------------------------
class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unbekannte Felder (z. B. company_id) -> 422

    projekt_name: Name
    budget_netto: Money
    status: ProjectStatus = ProjectStatus.aktiv
    start_datum: date = Field(default_factory=date.today)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projekt_name: str
    budget_netto: Decimal
    status: ProjectStatus
    start_datum: date
    created_at: datetime


class ProjectStatusRead(BaseModel):
    """Live-Kalkulation eines Projekts (alle Beträge netto)."""

    projekt_id: UUID
    projekt_name: str
    budget_netto: Decimal
    material_kosten: Decimal
    lohnkosten: Decimal
    gesamtkosten: Decimal
    restbudget: Decimal  # Budget - Material - Lohn (kann negativ sein)
    budget_verbrauch_prozent: Decimal | None  # None, wenn Budget = 0
    status_ampel: Ampel


# ----------------------------- Arbeitszeiten --------------------------
class WorkHourCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projekt_id: UUID
    datum: date
    mitarbeiter_name: Name
    stunden_anzahl: Hours
    stundensatz_intern: HourlyRate

    @field_validator("datum")
    @classmethod
    def _not_in_future(cls, v: date) -> date:
        # +1 Tag Toleranz wegen Zeitzonen (Server UTC vs. Handy in Europe/Berlin)
        if v > date.today() + timedelta(days=1):
            raise ValueError("Arbeitszeiten können nicht in der Zukunft gebucht werden.")
        return v


class WorkHourRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projekt_id: UUID
    datum: date
    mitarbeiter_name: str
    stunden_anzahl: Decimal
    stundensatz_intern: Decimal
    created_at: datetime


# ----------------------------- Material / Beleg-Import ----------------
import json as _json  # noqa: E402

Amount = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]  # negativ erlaubt (Gutschrift)


class ExtractedInvoice(BaseModel):
    """Von der KI vorgeschlagene Werte - alles optional, der Mensch prüft."""

    grosshaendler: str | None = None
    rechnungs_datum: date | None = None
    betrag_netto: Decimal | None = None


class ScanResult(BaseModel):
    extracted: ExtractedInvoice
    raw: dict  # Gemini-Rohantwort, wird beim Buchen als gemini_raw_json gespeichert


class MaterialCostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projekt_id: UUID
    rechnungs_datum: date
    grosshaendler: Name
    betrag_netto: Amount
    gemini_raw_json: dict | None = None

    @field_validator("gemini_raw_json")
    @classmethod
    def _limit_raw_size(cls, v: dict | None) -> dict | None:
        # kommt vom Client zurück -> Größe begrenzen (Missbrauchsschutz)
        if v is not None and len(_json.dumps(v)) > 20_000:
            raise ValueError("gemini_raw_json ist zu groß.")
        return v


class MaterialCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projekt_id: UUID
    rechnungs_datum: date
    grosshaendler: str
    betrag_netto: Decimal
    created_at: datetime


class ProjectEntries(BaseModel):
    """Alle Einzelbuchungen eines Projekts (neueste zuerst) für die Detailansicht."""

    material: list[MaterialCostRead]
    hours: list[WorkHourRead]


# ----------------------------- Bearbeiten (PATCH) ---------------------
from pydantic import EmailStr, model_validator  # noqa: E402


class WorkHourUpdate(BaseModel):
    """Teil-Update: nicht gesendete Felder bleiben unverändert."""

    model_config = ConfigDict(extra="forbid")

    datum: date | None = None
    mitarbeiter_name: Name | None = None
    stunden_anzahl: Hours | None = None
    stundensatz_intern: HourlyRate | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "WorkHourUpdate":
        if not self.model_fields_set:
            raise ValueError("Mindestens ein Feld angeben.")
        if self.datum and self.datum > date.today() + timedelta(days=1):
            raise ValueError("Arbeitszeiten können nicht in der Zukunft gebucht werden.")
        return self


class MaterialCostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rechnungs_datum: date | None = None
    grosshaendler: Name | None = None
    betrag_netto: Amount | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "MaterialCostUpdate":
        if not self.model_fields_set:
            raise ValueError("Mindestens ein Feld angeben.")
        return self


# ----------------------------- Team -----------------------------------
class MeRead(BaseModel):
    user_id: UUID
    company_id: UUID
    company_name: str
    role: Literal["owner", "admin", "member"]


class TeamMember(BaseModel):
    id: UUID
    email: str | None
    full_name: str | None
    role: Literal["owner", "admin", "member"]


class InviteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: Name | None = None
    role: Literal["admin", "member"] = "member"
