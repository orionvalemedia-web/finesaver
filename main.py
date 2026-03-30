from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import models
import database

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="finesaver-change-in-production")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

models.Base.metadata.create_all(bind=database.engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_ISSUES = {
    "taillight_out",
    "headlight_out",
    "gas_cap_open",
    "tire_issue",
    "door_trunk_open",
    "something_dragging",
    "other",
}

ISSUE_LABELS = {
    "taillight_out":      "Taillight Out",
    "headlight_out":      "Headlight Out",
    "gas_cap_open":       "Gas Cap Open",
    "tire_issue":         "Tire Issue",
    "door_trunk_open":    "Door / Trunk Open",
    "something_dragging": "Something Dragging",
    "other":              "Other",
}

# ── Rate limiting (in-memory: ip → list of submission timestamps) ─────────────
_report_log: dict = {}
RATE_LIMIT = 5
RATE_WINDOW = timedelta(hours=1)


def _is_rate_limited(ip: str) -> bool:
    now = datetime.utcnow()
    window_start = now - RATE_WINDOW
    times = _report_log.get(ip, [])
    times = [t for t in times if t > window_start]
    _report_log[ip] = times
    if len(times) >= RATE_LIMIT:
        return True
    times.append(now)
    _report_log[ip] = times
    return False


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Landing ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


# ── Register ──────────────────────────────────────────────────────────────────

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    plate: str = Form(...),
    phone: str = Form(""),
    db: Session = Depends(database.get_db),
):
    plate = plate.upper().strip()

    if db.query(models.User).filter(models.User.email == email).first():
        return templates.TemplateResponse(request, "register.html", {
            "error": "An account with this email already exists.",
        })

    if db.query(models.Vehicle).filter(models.Vehicle.plate == plate).first():
        return templates.TemplateResponse(request, "register.html", {
            "error": "This license plate is already registered.",
        })

    user = models.User(
        name=name,
        email=email,
        hashed_password=pwd_context.hash(password),
        phone=phone.strip() or None,
    )
    db.add(user)
    db.flush()

    vehicle = models.Vehicle(plate=plate, user_id=user.id)
    db.add(vehicle)
    db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=303)


# ── Login / Logout ────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse(request, "login.html", {
            "error": "Invalid email or password.",
        })
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


# ── Report ────────────────────────────────────────────────────────────────────

@app.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    return templates.TemplateResponse(request, "report.html", {})


@app.post("/report", response_class=HTMLResponse)
async def report(
    request: Request,
    plate: str = Form(...),
    issue: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(database.get_db),
):
    ip = _client_ip(request)
    if _is_rate_limited(ip):
        return templates.TemplateResponse(request, "confirmation.html", {
            "rate_limited": True,
        })

    plate = plate.upper().strip()

    if issue in VALID_ISSUES:
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate == plate).first()
        clean_note = note.strip()[:100] if issue == "other" and note.strip() else None
        entry = models.Report(
            plate=plate,
            issue=issue,
            note=clean_note,
            vehicle_id=vehicle.id if vehicle else None,
        )
        db.add(entry)
        db.commit()

    return RedirectResponse(url="/confirmation", status_code=303)


# ── Quick Report ──────────────────────────────────────────────────────────────

@app.get("/quick", response_class=HTMLResponse)
async def quick_report_page(request: Request):
    return templates.TemplateResponse(request, "quick_report.html", {})


@app.post("/quick", response_class=HTMLResponse)
async def quick_report(
    request: Request,
    plate: str = Form(...),
    issue: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(database.get_db),
):
    ip = _client_ip(request)
    if _is_rate_limited(ip):
        return templates.TemplateResponse(request, "confirmation.html", {
            "rate_limited": True,
        })

    plate = plate.upper().strip()

    if issue in VALID_ISSUES:
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate == plate).first()
        clean_note = note.strip()[:100] if issue == "other" and note.strip() else None
        entry = models.Report(
            plate=plate,
            issue=issue,
            note=clean_note,
            vehicle_id=vehicle.id if vehicle else None,
        )
        db.add(entry)
        db.commit()

    return RedirectResponse(url="/confirmation", status_code=303)


# ── Confirmation ──────────────────────────────────────────────────────────────

@app.get("/confirmation", response_class=HTMLResponse)
async def confirmation(request: Request):
    return templates.TemplateResponse(request, "confirmation.html", {
        "rate_limited": False,
    })


# ── Resolve Alert ─────────────────────────────────────────────────────────────

@app.post("/resolve/{report_id}")
async def resolve_alert(
    report_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == user.id).first()
    if vehicle:
        report = db.query(models.Report).filter(
            models.Report.id == report_id,
            models.Report.vehicle_id == vehicle.id,
        ).first()
        if report:
            report.resolved = True
            db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(database.get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == user.id).first()

    active_alerts = []
    resolved_alerts = []
    if vehicle:
        all_alerts = (
            db.query(models.Report)
            .filter(models.Report.vehicle_id == vehicle.id)
            .order_by(models.Report.timestamp.desc())
            .all()
        )
        active_alerts   = [a for a in all_alerts if not a.resolved]
        resolved_alerts = [a for a in all_alerts if a.resolved]

    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "vehicle": vehicle,
        "active_alerts": active_alerts,
        "resolved_alerts": resolved_alerts,
        "issue_labels": ISSUE_LABELS,
    })
