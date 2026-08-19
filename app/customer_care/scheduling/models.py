from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from customer_care.infrastructure.models import Base

# Maps to the scheduling.slot_status enum type T008's migration creates —
# create_type=False since this ORM class never creates/drops the type.
SlotStatus = PGEnum("available", "held", "booked", "blocked", name="slot_status", schema="scheduling", create_type=False)


class Specialty(Base):
    __tablename__ = "specialties"
    __table_args__ = {"schema": "scheduling"}
    specialty_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class Professional(Base):
    __tablename__ = "professionals"
    __table_args__ = {"schema": "scheduling"}
    professional_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean)


class ProfessionalSpecialty(Base):
    __tablename__ = "professional_specialties"
    __table_args__ = {"schema": "scheduling"}
    professional_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("scheduling.professionals.professional_id"), primary_key=True
    )
    specialty_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("scheduling.specialties.specialty_id"), primary_key=True
    )
    fixed_price_cents: Mapped[int] = mapped_column(Integer)
    appointment_duration_minutes: Mapped[int] = mapped_column(Integer)


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = {"schema": "scheduling"}
    unit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text)


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"
    __table_args__ = {"schema": "scheduling"}
    slot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    unit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.units.unit_id"))
    specialty_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.specialties.specialty_id"))
    professional_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.professionals.professional_id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(SlotStatus)
