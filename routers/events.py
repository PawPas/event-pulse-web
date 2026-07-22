import csv
import io
import itertools
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
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


class SampleRequest(BaseModel):
    count: int = Field(default=150, ge=1, le=250_000)


# 30 customer archetypes — 5 per RFM segment.
# Each tuple: (days_ago, event_type, amount_str)
# Timestamps are resolved at request time so recency scores stay stable.
_SAMPLE_TEMPLATES: list[dict] = [
    # --- Champions: R≥4 (recent ≤5 days), F≥4 (10–15 events), M≥4 (high spend) ---
    {"customer_id": "SAMPLE_C001", "events": [
        (1, "purchase", "199.99"), (1, "view", "0.00"), (2, "purchase", "149.00"),
        (2, "add_to_cart", "0.00"), (3, "purchase", "89.50"), (3, "view", "0.00"),
        (4, "purchase", "210.00"), (4, "add_to_cart", "0.00"), (5, "purchase", "175.00"),
        (5, "view", "0.00"), (5, "purchase", "99.00"),
    ]},
    {"customer_id": "SAMPLE_C002", "events": [
        (1, "purchase", "250.00"), (2, "view", "0.00"), (2, "purchase", "180.00"),
        (3, "add_to_cart", "0.00"), (3, "purchase", "120.00"), (4, "view", "0.00"),
        (4, "purchase", "95.00"), (5, "purchase", "310.00"), (5, "view", "0.00"),
        (5, "add_to_cart", "0.00"), (5, "purchase", "60.00"), (5, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C003", "events": [
        (2, "purchase", "399.00"), (2, "view", "0.00"), (3, "purchase", "220.00"),
        (3, "add_to_cart", "0.00"), (4, "purchase", "185.00"), (4, "view", "0.00"),
        (4, "purchase", "130.00"), (5, "view", "0.00"), (5, "purchase", "275.00"),
        (5, "add_to_cart", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C004", "events": [
        (1, "purchase", "155.00"), (1, "view", "0.00"), (2, "purchase", "200.00"),
        (3, "purchase", "90.00"), (3, "add_to_cart", "0.00"), (4, "purchase", "340.00"),
        (4, "view", "0.00"), (5, "purchase", "115.00"), (5, "view", "0.00"),
        (5, "add_to_cart", "0.00"), (5, "purchase", "80.00"),
    ]},
    {"customer_id": "SAMPLE_C005", "events": [
        (1, "purchase", "450.00"), (2, "view", "0.00"), (2, "purchase", "320.00"),
        (3, "add_to_cart", "0.00"), (3, "purchase", "210.00"), (4, "view", "0.00"),
        (4, "purchase", "175.00"), (4, "add_to_cart", "0.00"), (5, "purchase", "95.00"),
        (5, "view", "0.00"), (5, "purchase", "130.00"), (5, "view", "0.00"),
        (5, "purchase", "60.00"),
    ]},
    # --- Loyal Customers: F≥4, M≥4 but R<4 (last event 30–60 days ago) ---
    {"customer_id": "SAMPLE_C006", "events": [
        (30, "purchase", "189.00"), (35, "view", "0.00"), (40, "purchase", "225.00"),
        (45, "add_to_cart", "0.00"), (50, "purchase", "310.00"), (55, "view", "0.00"),
        (55, "purchase", "140.00"), (60, "add_to_cart", "0.00"), (60, "purchase", "95.00"),
    ]},
    {"customer_id": "SAMPLE_C007", "events": [
        (32, "purchase", "275.00"), (36, "view", "0.00"), (40, "purchase", "195.00"),
        (44, "add_to_cart", "0.00"), (48, "purchase", "350.00"), (52, "view", "0.00"),
        (56, "purchase", "120.00"), (60, "view", "0.00"), (60, "purchase", "88.00"),
    ]},
    {"customer_id": "SAMPLE_C008", "events": [
        (31, "purchase", "420.00"), (38, "view", "0.00"), (42, "purchase", "260.00"),
        (46, "add_to_cart", "0.00"), (50, "purchase", "180.00"), (54, "view", "0.00"),
        (58, "purchase", "310.00"), (60, "add_to_cart", "0.00"), (60, "view", "0.00"),
        (60, "purchase", "145.00"),
    ]},
    {"customer_id": "SAMPLE_C009", "events": [
        (33, "purchase", "155.00"), (37, "view", "0.00"), (41, "purchase", "290.00"),
        (45, "add_to_cart", "0.00"), (49, "purchase", "375.00"), (53, "view", "0.00"),
        (57, "purchase", "200.00"), (60, "view", "0.00"), (60, "purchase", "110.00"),
        (60, "add_to_cart", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C010", "events": [
        (30, "purchase", "330.00"), (35, "view", "0.00"), (39, "purchase", "245.00"),
        (43, "add_to_cart", "0.00"), (47, "purchase", "190.00"), (51, "view", "0.00"),
        (55, "purchase", "415.00"), (59, "view", "0.00"), (60, "purchase", "165.00"),
    ]},
    # --- Potential Loyalists: R≥4 (recent ≤14 days), F<4 (2–3 events) ---
    {"customer_id": "SAMPLE_C011", "events": [
        (3, "purchase", "49.99"), (7, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C012", "events": [
        (5, "purchase", "79.00"), (9, "add_to_cart", "0.00"), (14, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C013", "events": [
        (2, "purchase", "35.00"), (8, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C014", "events": [
        (6, "purchase", "59.99"), (10, "add_to_cart", "0.00"), (13, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C015", "events": [
        (4, "purchase", "44.00"), (11, "view", "0.00"),
    ]},
    # --- At Risk: R≤2 (last event 90–150 days ago), F≥3 (5–8 events) ---
    {"customer_id": "SAMPLE_C016", "events": [
        (90, "purchase", "85.00"), (100, "view", "0.00"), (110, "purchase", "120.00"),
        (120, "add_to_cart", "0.00"), (130, "view", "0.00"), (140, "purchase", "75.00"),
    ]},
    {"customer_id": "SAMPLE_C017", "events": [
        (92, "purchase", "110.00"), (102, "view", "0.00"), (112, "purchase", "95.00"),
        (122, "add_to_cart", "0.00"), (132, "view", "0.00"), (142, "purchase", "65.00"),
        (150, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C018", "events": [
        (95, "purchase", "140.00"), (105, "view", "0.00"), (115, "purchase", "80.00"),
        (125, "add_to_cart", "0.00"), (135, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C019", "events": [
        (91, "purchase", "70.00"), (101, "view", "0.00"), (111, "purchase", "100.00"),
        (121, "add_to_cart", "0.00"), (131, "view", "0.00"), (141, "purchase", "55.00"),
        (148, "view", "0.00"), (150, "add_to_cart", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C020", "events": [
        (93, "purchase", "90.00"), (103, "view", "0.00"), (113, "purchase", "115.00"),
        (123, "add_to_cart", "0.00"), (133, "view", "0.00"), (143, "purchase", "60.00"),
    ]},
    # --- Hibernating: R≤2 (last event 180–300 days ago), F≤2 (1–2 events) ---
    {"customer_id": "SAMPLE_C021", "events": [
        (180, "purchase", "25.00"),
    ]},
    {"customer_id": "SAMPLE_C022", "events": [
        (200, "view", "0.00"), (220, "purchase", "19.99"),
    ]},
    {"customer_id": "SAMPLE_C023", "events": [
        (250, "purchase", "30.00"),
    ]},
    {"customer_id": "SAMPLE_C024", "events": [
        (270, "view", "0.00"), (290, "purchase", "22.00"),
    ]},
    {"customer_id": "SAMPLE_C025", "events": [
        (300, "purchase", "15.00"),
    ]},
    # --- Others: R=3 (20–45 days), F=3 (middling), M=2–3 ---
    {"customer_id": "SAMPLE_C026", "events": [
        (20, "purchase", "39.00"), (30, "view", "0.00"), (40, "purchase", "29.00"),
    ]},
    {"customer_id": "SAMPLE_C027", "events": [
        (22, "view", "0.00"), (32, "purchase", "45.00"), (42, "add_to_cart", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C028", "events": [
        (25, "purchase", "55.00"), (35, "view", "0.00"), (45, "purchase", "33.00"),
        (45, "add_to_cart", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C029", "events": [
        (21, "view", "0.00"), (31, "purchase", "48.00"), (41, "view", "0.00"),
    ]},
    {"customer_id": "SAMPLE_C030", "events": [
        (24, "purchase", "42.00"), (34, "add_to_cart", "0.00"), (44, "purchase", "36.00"),
    ]},
]


class UploadResult(BaseModel):
    events_added: int


def _parse_record(row: object, row_num: int) -> tuple[Event | None, str | None]:
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
    reader = csv.DictReader(io.StringIO(content))
    required = {"customer_id", "timestamp", "event_type", "amount"}
    fieldnames = set(reader.fieldnames or [])
    missing_cols = required - fieldnames
    if missing_cols:
        return [], f"CSV is missing required column(s): {', '.join(sorted(missing_cols))}"
    return list(reader), None


def _parse_json(content: str) -> tuple[list, str | None]:
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
            if event is None:
                continue
            event.report_id = report_id
            events.append(event)

    if total_invalid > 0:
        detail = f"Validation failed: {total_invalid} invalid record(s). Sample errors: {'; '.join(sample_errors)}"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    # 7. Bulk insert in a single transaction
    db.add_all(events)
    await db.commit()

    return UploadResult(events_added=len(events))


@router.post(
    "/{report_id}/events/sample",
    status_code=status.HTTP_200_OK,
    response_model=UploadResult,
)
async def generate_sample_events(
    report_id: UUID,
    payload: SampleRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> UploadResult:
    resolved = payload or SampleRequest()

    # 1. Verify report ownership
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == UUID(current_user.sub))
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # 2. Cap check: existing + requested must not exceed 200k
    count_result = await db.execute(
        select(func.count(Event.id)).where(Event.report_id == report_id)
    )
    existing = count_result.scalar_one()
    if existing + resolved.count > _MAX_EVENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot generate {resolved.count:,} events: report already has {existing:,} events "
                f"and the 200,000-event limit would be exceeded"
            ),
        )

    # 3. Build flat event list from templates, cycling to reach resolved.count
    base: list[tuple[str, int, str, str]] = []
    for template in _SAMPLE_TEMPLATES:
        cid = template["customer_id"]
        for days_ago, event_type, amount_str in template["events"]:
            base.append((cid, days_ago, event_type, amount_str))

    now = datetime.now(timezone.utc)
    events: list[Event] = [
        Event(
            report_id=report_id,
            customer_id=cid,
            timestamp=now - timedelta(days=days_ago),
            event_type=event_type,
            amount=Decimal(amount_str),
        )
        for cid, days_ago, event_type, amount_str in itertools.islice(
            itertools.cycle(base), resolved.count
        )
    ]

    db.add_all(events)
    await db.commit()

    return UploadResult(events_added=resolved.count)
