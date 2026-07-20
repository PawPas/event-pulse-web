import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.schemas import TokenPayload
from database import get_db
from models.event import Event
from models.report import Report

router = APIRouter(prefix="/api/reports", tags=["events"])

_SUPPORTED_EXTENSIONS = {".csv", ".json"}
_MAX_EVENTS = 200_000
_MAX_SAMPLE_ERRORS = 5


class UploadResult(BaseModel):
    events_added: int


def _parse_record(row: object, row_num: int) -> tuple[Event | None, str | None]:
    """Validate one record dict and return an Event or an error message."""
    if not isinstance(row, dict):
        return None, f"Row {row_num}: expected an object, got {type(row).__name__}"

    missing = [f for f in ("customer_id", "timestamp", "event_type", "amount") if not row.get(f) and row.get(f) != 0]
    if missing:
        return None, f"Row {row_num}: missing required field(s): {', '.join(missing)}"

    try:
        dt = datetime.fromisoformat(str(row["timestamp"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None, f"Row {row_num}: invalid timestamp '{row['timestamp']}'"

    try:
        amount = Decimal(str(row["amount"]))
    except (InvalidOperation, TypeError):
        return None, f"Row {row_num}: invalid amount '{row['amount']}'"

    return (
        Event(
            customer_id=str(row["customer_id"]),
            timestamp=dt,
            event_type=str(row["event_type"]),
            amount=amount,
        ),
        None,
    )


def _parse_csv(content: str) -> tuple[list[dict], str | None]:
    """Parse CSV string; return (rows, error_message). error_message is set on structural errors."""
    reader = csv.DictReader(io.StringIO(content))
    required = {"customer_id", "timestamp", "event_type", "amount"}
    fieldnames = set(reader.fieldnames or [])
    missing_cols = required - fieldnames
    if missing_cols:
        return [], f"CSV is missing required column(s): {', '.join(sorted(missing_cols))}"
    return list(reader), None


def _parse_json(content: str) -> tuple[list, str | None]:
    """Parse JSON string; return (items, error_message)."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return [], f"Invalid JSON: {exc}"
    if not isinstance(data, list):
        return [], "JSON file must be an array of event objects"
    return data, None


@router.post(
    "/{report_id}/events/upload",
    status_code=status.HTTP_200_OK,
    response_model=UploadResult,
)
async def upload_events(
    report_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> UploadResult:
    # 1. Validate filename and extension first (before touching the file body)
    filename = file.filename
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a .csv or .json extension",
        )
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Upload a .csv or .json file",
        )

    # 2. Verify report ownership
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == UUID(current_user.sub))
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # 3. Read and decode file
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded",
        )

    # 4. Parse into a list of raw rows
    if ext == ".csv":
        rows, parse_error = _parse_csv(content)
    else:
        rows, parse_error = _parse_json(content)

    if parse_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=parse_error)
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File contains no event records")

    # 5. Count check before per-record validation (PRD: reject at upload boundary)
    if len(rows) > _MAX_EVENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File contains {len(rows)} events which exceeds the 200,000-event limit",
        )

    # 6. Per-record validation — collect up to 5 error samples
    events: list[Event] = []
    sample_errors: list[str] = []
    total_invalid = 0

    for i, row in enumerate(rows, start=1):
        event, error = _parse_record(row, i)
        if error:
            total_invalid += 1
            if len(sample_errors) < _MAX_SAMPLE_ERRORS:
                sample_errors.append(error)
        else:
            assert event is not None
            event.report_id = report_id
            events.append(event)

    if total_invalid > 0:
        detail = f"Validation failed: {total_invalid} invalid record(s). Sample errors: {'; '.join(sample_errors)}"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    # 7. Bulk insert in a single transaction
    db.add_all(events)
    await db.commit()

    return UploadResult(events_added=len(events))
