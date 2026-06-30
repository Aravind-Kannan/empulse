from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tenure_years: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    manager_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )

    manager: Mapped["Employee | None"] = relationship(
        "Employee", remote_side="Employee.id", back_populates="direct_reports"
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="manager"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="employee", cascade="all, delete-orphan"
    )


class Component(Base):
    __tablename__ = "components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    open_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unresolved_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="component", cascade="all, delete-orphan"
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False
    )
    component_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=False
    )
    codebase_share_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="assignments")
    component: Mapped["Component"] = relationship("Component", back_populates="assignments")
