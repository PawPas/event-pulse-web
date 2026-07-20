from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.schemas import TokenPayload
from database import get_db
from models.event import Event
from models.report import Report

router = APIRouter(prefix="/api/reports", tags=["reports"])


class CreateReportRequest(BaseModel):
    name: str
    description: str | None = None


class ReportResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    event_count: int
    analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _event_count_sq():
    return (
        select(func.count(Event.id))
        .where(Event.report_id == Report.id)
        .correlate(Report)
        .scalar_subquery()
    )


def _row_to_response(row) -> ReportResponse:
    r = row.Report
    return ReportResponse(
        id=str(r.id),
        name=r.name,
        description=r.description,
        status=r.status.value,
        event_count=row.event_count,
        analyzed_at=r.analyzed_at,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ReportResponse)
async def create_report(
    payload: CreateReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> ReportResponse:
    report = Report(
        user_id=UUID(current_user.sub),
        name=payload.name,
        description=payload.description,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return ReportResponse(
        id=str(report.id),
        name=report.name,
        description=report.description,
        status=report.status.value,
        event_count=0,
        analyzed_at=report.analyzed_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[ReportResponse])
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> list[ReportResponse]:
    event_count_sq = _event_count_sq()
    stmt = (
        select(Report, event_count_sq.label("event_count"))
        .where(Report.user_id == UUID(current_user.sub))
        .order_by(Report.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_row_to_response(row) for row in rows]


@router.get("/{report_id}", status_code=status.HTTP_200_OK, response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> ReportResponse:
    event_count_sq = _event_count_sq()
    stmt = (
        select(Report, event_count_sq.label("event_count"))
        .where(Report.id == report_id, Report.user_id == UUID(current_user.sub))
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return _row_to_response(row)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if report is None or report.user_id != UUID(current_user.sub):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    await db.delete(report)
    await db.commit()
