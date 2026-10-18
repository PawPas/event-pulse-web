import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.schemas import TokenPayload
from database import get_db, get_session_factory
from models.event import Event
from models.report import Report, ReportStatus
from services.rfm import compute_rfm

router = APIRouter(prefix="/api/reports", tags=["reports"])


class CustomerResult(BaseModel):
    customer_id: str
    segment: str
    r_score: int
    f_score: int
    m_score: int
    recency_days: int
    frequency: int
    monetary: float


class AnalysisResult(BaseModel):
    unique_customers: int
    segment_counts: dict[str, int]
    customers: list[CustomerResult]


class RunAnalysisResponse(BaseModel):
    status: str


async def _run_analysis(report_id: UUID) -> None:
    async with get_session_factory()() as db:
        try:
            result = await db.execute(select(Report).where(Report.id == report_id))
            report = result.scalar_one_or_none()
            if report is None:
                return

            events_result = await db.execute(
                select(Event)
                .where(Event.report_id == report_id)
                .order_by(Event.timestamp)
            )
            events = events_result.scalars().all()

            analysis_ts = datetime.now(timezone.utc)
            event_dicts = [
                {
                    "customer_id": e.customer_id,
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "amount": e.amount,
                }
                for e in events
            ]

            result_data = compute_rfm(event_dicts, analysis_ts)

            report.analysis_result = result_data
            report.analyzed_at = analysis_ts
            report.status = ReportStatus.completed
            await db.commit()

        except Exception:
            logging.exception("_run_analysis failed for report %s", report_id)
            try:
                await db.rollback()
                result = await db.execute(select(Report).where(Report.id == report_id))
                report = result.scalar_one_or_none()
                if report is not None:
                    report.status = ReportStatus.failed
                    await db.commit()
            except Exception:
                logging.exception("Failed to set report %s to failed", report_id)


@router.post(
    "/{report_id}/analysis/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunAnalysisResponse,
)
async def run_analysis(
    report_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> RunAnalysisResponse:
    event_count_sq = (
        select(func.count(Event.id))
        .where(Event.report_id == report_id)
        .scalar_subquery()
    )
    stmt = select(Report, event_count_sq.label("event_count")).where(
        Report.id == report_id,
        Report.user_id == UUID(current_user.sub),
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report, event_count = row.Report, row.event_count

    if report.status == ReportStatus.analyzing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis already in progress",
        )

    if event_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report has no events to analyse",
        )

    report.status = ReportStatus.analyzing
    await db.commit()
    background_tasks.add_task(_run_analysis, report_id)

    return RunAnalysisResponse(status="analyzing")


@router.get(
    "/{report_id}/analysis/results",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisResult,
)
async def get_analysis_results(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> AnalysisResult:
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == UUID(current_user.sub),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.status == ReportStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis failed — please re-run",
        )

    if report.analysis_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis results — run analysis first",
        )

    try:
        return AnalysisResult(**report.analysis_result)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored analysis result is corrupted",
        )
