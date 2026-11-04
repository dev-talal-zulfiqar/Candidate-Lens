from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.resume import Resume


class Candidate(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "candidates"

    display_name: Mapped[str | None] = mapped_column(default=None)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate")
    applications: Mapped[list["Application"]] = relationship(back_populates="candidate")
