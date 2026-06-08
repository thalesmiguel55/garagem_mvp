import os
import sqlite3
import uuid
import json
import requests
import threading
import time
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict
from requests.auth import HTTPBasicAuth
from fastapi import (
    FastAPI, UploadFile, File, Form, HTTPException,
    Query, Header, Depends, Cookie, Response
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DB_PATH = "garagem.db"
UPLOAD_DIR = "uploads"
CONFIG_PATH = "config.json"
IP_RELE = "192.168.88.231"
PORTA = 80
USUARIO = "admin"
SENHA = "admin"
app = FastAPI(title="Garagem MVP")


def carregar_config() -> Dict:
    if not os.path.isfile(CONFIG_PATH):
        return {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Erro ao ler config.json:", e)
        return {}


CONFIG = carregar_config()
TELEGRAM_CONFIG = CONFIG.get("telegram", {})
HARDWARE_CONFIG = CONFIG.get("hardware", {})
ALERTAS_CONFIG = CONFIG.get("alertas", {})
LIBERACAO_CAIXAS_HABILITADA = bool(HARDWARE_CONFIG.get("habilitar_liberacao_caixas", False))
RETIRADA_ALERTA_HORAS = float(ALERTAS_CONFIG.get("horas_retirada", 8))
RETIRADA_ALERTA_INTERVALO_SEG = int(ALERTAS_CONFIG.get("intervalo_verificacao_minutos", 15)) * 60


def acionar_rele(estado="on"):
    url = f"http://{IP_RELE}:{PORTA}/"
    params = {
        "request": "relay",
        "state": estado
    }

    try:
        r = requests.get(
            url,
            params=params,
            auth=HTTPBasicAuth(USUARIO, SENHA),
            timeout=5
        )
        print("Status HTTP:", r.status_code)
        print("Resposta:", r.text)
        return r.status_code == 200
    except requests.RequestException as e:
        print("Erro ao acionar relé:", e)
        return False


def status_rele():
    url = f"http://{IP_RELE}:{PORTA}/"

    try:
        r = requests.get(
            url,
            params={"request": "status"},
            auth=HTTPBasicAuth(USUARIO, SENHA),
            timeout=5
        )
        print("Status HTTP:", r.status_code)
        print("Resposta:", r.text)
        return {
            "ok": r.status_code == 200,
            "statusCode": r.status_code,
            "body": r.text,
        }
    except requests.RequestException as e:
        print("Erro ao consultar sensor da fechadura:", e)
        return {
            "ok": False,
            "error": str(e),
        }


DEFAULT_VEHICLES = [
    ("AAA1A11/PORTARIA", 1),
    ("BBB2B22/MANUTENÇÃO", 2),
]

# ===== Admin =====
ADMIN_PASSWORD = os.environ.get("GARAGEM_ADMIN_PASSWORD", "admin123")  # MUDE ISSO!
TOKEN_TTL_SECONDS = 60 * 60 * 8  # 8 horas
ADMIN_TOKENS: Dict[str, float] = {}  # token -> expires_epoch
TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    str(TELEGRAM_CONFIG.get("bot_token", "")),
).strip()
TELEGRAM_CHAT_ID = os.environ.get(
    "TELEGRAM_CHAT_ID",
    str(TELEGRAM_CONFIG.get("chat_id", "")),
).strip()
TELEGRAM_TIMEOUT = float(os.environ.get(
    "TELEGRAM_TIMEOUT",
    str(TELEGRAM_CONFIG.get("timeout", "5")),
))
ESP32_IP = "http://192.168.0.50/abrir"
TOKEN = "123seguro"

@app.get("/api/abrir")
def abrir_fechadura(caixa: int = 1):
    ok = abrir_caixa(caixa)
    if not ok:
        raise HTTPException(status_code=502, detail=f"Não foi possível acionar a fechadura da caixa {caixa}.")
    return {"ok": True, "message": f"Fechadura da caixa {caixa} acionada."}


@app.post("/api/liberar-caixa")
def liberar_caixa(vehicle_plate: str = Form(...)):
    if not plate_is_registered(vehicle_plate):
        raise HTTPException(status_code=400, detail="Placa inválida.")

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, checkout_user, checkout_at
        FROM assignments
        WHERE status='OPEN' AND vehicle_plate=?
        LIMIT 1
    """, (vehicle_plate,))
    row = cur.fetchone()
    conn.close()

    if row:
        raise HTTPException(
            status_code=409,
            detail=f"Esta placa já está em uso. Retirado por {row['checkout_user']} em {row['checkout_at']}."
        )

    caixa = definir_caixa(vehicle_plate)
    if LIBERACAO_CAIXAS_HABILITADA:
        if not caixa:
            raise HTTPException(status_code=400, detail="Caixa não configurada para esta placa.")

        ok = abrir_caixa(caixa)
        if not ok:
            raise HTTPException(status_code=502, detail=f"Não foi possível acionar a fechadura da caixa {caixa}.")

        return {"ok": True, "caixa": caixa, "message": f"Fechadura da caixa {caixa} acionada."}

    return {
        "ok": True,
        "caixa": caixa,
        "message": "Liberação de caixas desabilitada. Registro liberado sem acionar fechadura.",
    }


@app.get("/api/status-fechadura")
def status_fechadura(caixa: int = 1):
    if int(caixa) != 1:
        raise HTTPException(status_code=400, detail="Sensor integrado apenas para a caixa 1.")

    status = status_rele()
    if not status["ok"]:
        raise HTTPException(status_code=502, detail=status)

    return {
        "ok": True,
        "caixa": caixa,
        "sensor": status["body"],
    }


def abrir_caixa_esp(caixa):
    try:
        r = requests.get(f"{ESP32_IP}?caixa={caixa}&token={TOKEN}", timeout=2)
        print("ESP32 caixa:", caixa, "Status HTTP:", r.status_code)
        print("Resposta:", r.text)
        return r.status_code == 200
    except requests.RequestException as e:
        print("Erro ao abrir caixa:", e)
        return False


def abrir_caixa(caixa):
    if not LIBERACAO_CAIXAS_HABILITADA:
        print(f"Liberação de caixas desabilitada. Ignorando abertura da caixa {caixa}.")
        return True

    if int(caixa) == 1:
        return acionar_rele("on")

    return abrir_caixa_esp(caixa)


def abrir_caixa_async(caixa):
    threading.Thread(target=abrir_caixa, args=(caixa,), daemon=True).start()


def enviar_telegram(texto: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram não configurado em config.json.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT)
        if r.status_code != 200:
            print("Erro Telegram HTTP:", r.status_code, r.text)
            return False
        return True
    except requests.RequestException as e:
        print("Erro ao enviar Telegram:", e)
        return False


def enviar_telegram_async(texto: str):
    threading.Thread(target=enviar_telegram, args=(texto,), daemon=True).start()


def parse_iso_datetime(value: str) -> datetime:
    normalized = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def formatar_duracao(total_seconds: int) -> str:
    horas, resto = divmod(max(total_seconds, 0), 3600)
    minutos, _ = divmod(resto, 60)
    if horas and minutos:
        return f"{horas}h {minutos}min"
    if horas:
        return f"{horas}h"
    return f"{minutos}min"


def formatar_data_hora_local(value: str) -> str:
    try:
        parsed = parse_iso_datetime(value).astimezone()
        return parsed.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value or "-")


def verificar_retiradas_prolongadas():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    limite_segundos = int(RETIRADA_ALERTA_HORAS * 3600)
    agora = datetime.now(timezone.utc)

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, vehicle_plate, checkout_at, checkout_user
        FROM assignments
        WHERE status='OPEN' AND overdue_alert_sent_at IS NULL
    """)
    rows = cur.fetchall()

    for row in rows:
        try:
            checkout_at = parse_iso_datetime(row["checkout_at"])
        except Exception:
            print("Retirada com data inválida:", row["id"], row["checkout_at"])
            continue

        duracao = agora - checkout_at
        if duracao.total_seconds() < limite_segundos:
            continue

        mensagem = (
            "⚠️ Retirada prolongada\n"
            f"Carro/placa: {row['vehicle_plate']}\n"
            f"Quem retirou: {row['checkout_user']}\n"
            f"Retirado em: {formatar_data_hora_local(row['checkout_at'])}\n"
            f"Tempo em uso: {formatar_duracao(int(duracao.total_seconds()))}\n"
            f"Limite configurado: {int(RETIRADA_ALERTA_HORAS)} horas"
        )

        if not enviar_telegram(mensagem):
            continue

        cur.execute("""
            UPDATE assignments
            SET overdue_alert_sent_at=?
            WHERE id=? AND status='OPEN' AND overdue_alert_sent_at IS NULL
        """, (agora.isoformat(), row["id"]))

    conn.commit()
    conn.close()


def loop_monitor_retiradas():
    while True:
        try:
            verificar_retiradas_prolongadas()
        except Exception as e:
            print("Erro no monitor de retiradas prolongadas:", e)
        time.sleep(max(RETIRADA_ALERTA_INTERVALO_SEG, 60))


def listar_avarias_checklist(answers: Dict) -> list[str]:
    labels = {
        "retrovisores": "Retrovisores",
        "pneus": "Pneus",
        "farois": "Faróis",
        "lataria": "Lataria",
    }
    return [
        label
        for key, label in labels.items()
        if str(answers.get(key, "")).lower() in ["no", "nao", "não", "false"]
    ]


def normalize_plate_part(plate: str) -> str:
    return plate.strip().upper().replace(" ", "")


def build_vehicle_plate(plate: str, description: str = "") -> str:
    normalized = normalize_plate_part(plate)
    desc = description.strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="Informe a placa do veículo.")
    if desc:
        return f"{normalized}/{desc}"
    return normalized


def vehicle_usage_status(vehicle: Dict, open_plates: set[str]) -> str:
    if int(vehicle.get("active", 1)) != 1:
        return "INACTIVE"
    if vehicle["plate"] in open_plates:
        return "IN_USE"
    return "AVAILABLE"


def parse_caixa_value(caixa: Optional[str]) -> Optional[int]:
    if caixa is None or not str(caixa).strip():
        return None

    try:
        value = int(str(caixa).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Número da caixa inválido.")

    if value < 1:
        raise HTTPException(status_code=400, detail="Número da caixa deve ser maior que zero.")

    return value


def list_active_plates() -> list[str]:
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT plate
        FROM vehicles
        WHERE active=1
        ORDER BY plate ASC
    """)
    plates = [row["plate"] for row in cur.fetchall()]
    conn.close()
    return plates


def plate_is_registered(vehicle_plate: str) -> bool:
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM vehicles
        WHERE plate=? AND active=1
        LIMIT 1
    """, (vehicle_plate,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def definir_caixa(plate):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT caixa
        FROM vehicles
        WHERE plate=? AND active=1
        LIMIT 1
    """, (plate,))
    row = cur.fetchone()
    conn.close()

    if row and row["caixa"] is not None:
        return int(row["caixa"])
    return None

def _prune_tokens():
    now = time.time()
    expired = [t for t, exp in ADMIN_TOKENS.items() if exp <= now]
    for t in expired:
        ADMIN_TOKENS.pop(t, None)


def require_admin(
    x_admin_token: Optional[str] = Header(None),
    admin_token: Optional[str] = Cookie(None),
):
    _prune_tokens()
    token = x_admin_token or admin_token
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    exp = ADMIN_TOKENS.get(token)
    if not exp:
        raise HTTPException(status_code=401, detail="Sessão inválida. Faça login novamente.")
    if exp <= time.time():
        ADMIN_TOKENS.pop(token, None)
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente.")

    return True


os.makedirs("static", exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id TEXT PRIMARY KEY,
        vehicle_plate TEXT NOT NULL,
        status TEXT NOT NULL, -- OPEN / CLOSED
        checkout_at TEXT NOT NULL,
        checkin_at TEXT,
        checkout_user TEXT NOT NULL,
        checkin_user TEXT,
        checkout_answers TEXT,
        checkin_answers TEXT,
        overdue_alert_sent_at TEXT
    )
    """)

    cur.execute("PRAGMA table_info(assignments)")
    assignment_columns = {row[1] for row in cur.fetchall()}
    if "overdue_alert_sent_at" not in assignment_columns:
        cur.execute("ALTER TABLE assignments ADD COLUMN overdue_alert_sent_at TEXT")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS photos (
        id TEXT PRIMARY KEY,
        assignment_id TEXT NOT NULL,
        phase TEXT NOT NULL, -- CHECKOUT / CHECKIN
        slot TEXT NOT NULL,  -- front/rear/left/right/interior/selfie/issue_*
        path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id TEXT PRIMARY KEY,
        plate TEXT NOT NULL UNIQUE,
        caixa INTEGER,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("SELECT COUNT(*) AS total FROM vehicles")
    if cur.fetchone()["total"] == 0:
        now = datetime.now(timezone.utc).isoformat()
        for plate, caixa in DEFAULT_VEHICLES:
            cur.execute("""
                INSERT INTO vehicles (id, plate, caixa, active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (str(uuid.uuid4()), plate, caixa, now))

    conn.commit()
    conn.close()


init_db()


@app.on_event("startup")
def iniciar_monitor_retiradas():
    threading.Thread(target=loop_monitor_retiradas, daemon=True).start()
    print(
        "Monitor de retiradas prolongadas ativo: "
        f"{int(RETIRADA_ALERTA_HORAS)}h, verificação a cada "
        f"{max(RETIRADA_ALERTA_INTERVALO_SEG // 60, 1)} min."
    )


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/admin")
def admin_page():
    return FileResponse("static/admin.html")


@app.get("/api/context")
def get_context():
    """
    Retorna status por placa (AVAILABLE / IN_USE) + lista de retiradas OPEN (para devolução).
    """
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, vehicle_plate, checkout_at, checkout_user
        FROM assignments
        WHERE status='OPEN'
        ORDER BY checkout_at DESC
    """)
    open_rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    open_by_plate = {r["vehicle_plate"]: r for r in open_rows}

    plates = []
    for p in list_active_plates():
        if p in open_by_plate:
            plates.append({
                "plate": p,
                "status": "IN_USE",
                "openAssignment": {
                    "id": open_by_plate[p]["id"],
                    "vehiclePlate": open_by_plate[p]["vehicle_plate"],
                    "checkoutAt": open_by_plate[p]["checkout_at"],
                    "checkoutUser": open_by_plate[p]["checkout_user"],
                }
            })
        else:
            plates.append({"plate": p, "status": "AVAILABLE"})

    return {
        "liberacaoCaixasHabilitada": LIBERACAO_CAIXAS_HABILITADA,
        "plates": plates,
        "openAssignments": [
            {
                "id": r["id"],
                "vehiclePlate": r["vehicle_plate"],
                "checkoutAt": r["checkout_at"],
                "checkoutUser": r["checkout_user"],
            }
            for r in open_rows
        ]
    }


async def _save_upload_image(cur, assignment_id: str, phase: str, slot: str, up: UploadFile, now: str):
    """
    Salva mantendo extensão real (evita miniatura quebrada).
    """
    ext = os.path.splitext(up.filename or "")[1].lower()
    ext_by_ct = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"]:
        ext = ext_by_ct.get((up.content_type or "").lower(), ".jpg")

    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"]:
        raise HTTPException(status_code=400, detail=f"Formato inválido em {slot}. Use jpg/png/webp/heic.")

    filename = f"{assignment_id}_{phase}_{slot}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    content = await up.read()
    if len(content) < 10_000:
        raise HTTPException(status_code=400, detail=f"Arquivo {slot} parece inválido.")

    with open(path, "wb") as f:
        f.write(content)

    cur.execute("""
        INSERT INTO photos (id, assignment_id, phase, slot, path, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), assignment_id, phase, slot, path, now))


@app.post("/api/checkout")
async def checkout(
    vehicle_plate: str = Form(...),
    user: str = Form(...),
    answers_json: str = Form("{}"),
    box_released: bool = Form(False),

    # fotos externas do carro
    front: UploadFile = File(...),
    rear: UploadFile = File(...),
    left: UploadFile = File(...),
    right: UploadFile = File(...),
    interior: Optional[UploadFile] = File(None),

    # selfie
    selfie: UploadFile = File(...),

    # issues (opcional; obrigatório se answers_json marcar "no")
    issue_retrovisores: Optional[UploadFile] = File(None),
    issue_pneus: Optional[UploadFile] = File(None),
    issue_farois: Optional[UploadFile] = File(None),
    issue_lataria: Optional[UploadFile] = File(None),
):
    if not plate_is_registered(vehicle_plate):
        raise HTTPException(status_code=400, detail="Placa inválida.")
    if not user or not user.strip():
        raise HTTPException(status_code=400, detail="Informe o nome do funcionário.")

    conn = db()
    cur = conn.cursor()

    # bloqueio por placa (não deixa retirar se já estiver OPEN)
    cur.execute("""
        SELECT id, checkout_user, checkout_at
        FROM assignments
        WHERE status='OPEN' AND vehicle_plate=?
        LIMIT 1
    """, (vehicle_plate,))
    row = cur.fetchone()
    if row:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Esta placa já está em uso. Retirado por {row['checkout_user']} em {row['checkout_at']}."
        )

    try:
        answers = json.loads(answers_json or "{}")
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="answers_json inválido.")

    issue_files = {
        "retrovisores": issue_retrovisores,
        "pneus": issue_pneus,
        "farois": issue_farois,
        "lataria": issue_lataria,
    }

    for key, up in issue_files.items():
        if (answers.get(key) or "").lower() == "no" and up is None:
            conn.close()
            raise HTTPException(status_code=400, detail=f'Você marcou "{key}" como NÃO. Envie a foto do problema.')

    assignment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cur.execute("""
        INSERT INTO assignments (id, vehicle_plate, status, checkout_at, checkout_user, checkout_answers)
        VALUES (?, ?, 'OPEN', ?, ?, ?)
    """, (assignment_id, vehicle_plate, now, user.strip(), answers_json))

    if LIBERACAO_CAIXAS_HABILITADA and not box_released:
        caixa = definir_caixa(vehicle_plate)
        if caixa:
            abrir_caixa_async(caixa)

    try:
        await _save_upload_image(cur, assignment_id, "CHECKOUT", "front", front, now)
        await _save_upload_image(cur, assignment_id, "CHECKOUT", "rear", rear, now)
        await _save_upload_image(cur, assignment_id, "CHECKOUT", "left", left, now)
        await _save_upload_image(cur, assignment_id, "CHECKOUT", "right", right, now)
        if interior is not None:
            await _save_upload_image(cur, assignment_id, "CHECKOUT", "interior", interior, now)

        await _save_upload_image(cur, assignment_id, "CHECKOUT", "selfie", selfie, now)

        for key, up in issue_files.items():
            if (answers.get(key) or "").lower() == "no":
                await _save_upload_image(cur, assignment_id, "CHECKOUT", f"issue_{key}", up, now)

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno ao salvar arquivos.")
    finally:
        conn.close()

    enviar_telegram_async(
        "❗ Carro retirado\n"
        f"Carro/placa: {vehicle_plate}\n"
        f"Quem retirou: {user.strip()}"
    )

    return {"ok": True, "assignmentId": assignment_id, "message": "Retirada registrada e arquivos salvos com sucesso."}

@app.post("/api/checkin")
async def checkin(
    assignment_id: str = Form(...),
    user: str = Form(...),
    answers_json: str = Form("{}"),
    interior: UploadFile = File(...),
):
    if not user or not user.strip():
        raise HTTPException(status_code=400, detail="Informe o nome do funcionário que está devolvendo.")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM assignments WHERE id=? AND status='OPEN'", (assignment_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Nenhuma retirada aberta encontrada para esse ID.")

    try:
        checkin_answers = json.loads(answers_json or "{}")
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="answers_json inválido.")

    try:
        checkout_answers = json.loads(row["checkout_answers"] or "{}")
    except Exception:
        checkout_answers = {}

    now = datetime.now(timezone.utc).isoformat()
    try:
        cur.execute("""
            UPDATE assignments
            SET status='CLOSED', checkin_at=?, checkin_user=?, checkin_answers=?
            WHERE id=?
        """, (now, user.strip(), answers_json, assignment_id))
        await _save_upload_image(cur, assignment_id, "CHECKIN", "interior", interior, now)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno ao salvar arquivos.")
    finally:
        conn.close()

    vehicle_plate = row["vehicle_plate"]

    if LIBERACAO_CAIXAS_HABILITADA:
        caixa = definir_caixa(vehicle_plate)
        if caixa:
            abrir_caixa_async(caixa)

    avarias_retirada = listar_avarias_checklist(checkout_answers)
    avarias_entrega = str(checkin_answers.get("obs", "")).strip()
    mensagem_entrega = (
        "✔️ Carro entregue/devolvido\n"
        f"Carro/placa: {vehicle_plate}\n"
        f"Quem entregou: {user.strip()}"
    )
    if avarias_entrega:
        mensagem_entrega += f"\nAvarias na entrega: {avarias_entrega}"
    if avarias_retirada:
        mensagem_entrega += "\nAvarias já registradas na retirada: " + ", ".join(avarias_retirada)

    enviar_telegram_async(mensagem_entrega)

    return {"ok": True, "message": "Devolução registrada. Obrigado!"}


# ===== UPLOADS (PROTEGIDO - ADMIN ONLY) =====
@app.get("/uploads/{filename}")
def get_upload(filename: str, _=Depends(require_admin)):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(path)


# ===== ADMIN AUTH (cookie) =====
@app.post("/api/admin/login")
def admin_login(password: str = Form(...), response: Response = None):
    # assinatura correta (FastAPI injeta Response automaticamente)
    # aqui deixamos sem risco: se vier None, criaremos um Response local
    if response is None:
        response = Response()

    _prune_tokens()
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Senha inválida.")

    token = secrets.token_urlsafe(32)
    ADMIN_TOKENS[token] = time.time() + TOKEN_TTL_SECONDS

    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=TOKEN_TTL_SECONDS,
        path="/",
        secure=False,  # True quando estiver em HTTPS
    )
    return {"ok": True, "expiresIn": TOKEN_TTL_SECONDS}


@app.post("/api/admin/logout")
def admin_logout(response: Response, admin_token: Optional[str] = Cookie(None)):
    if admin_token:
        ADMIN_TOKENS.pop(admin_token, None)
    response.delete_cookie("admin_token", path="/")
    return {"ok": True}


@app.get("/api/admin/vehicles")
def admin_list_vehicles(_=Depends(require_admin)):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT vehicle_plate
        FROM assignments
        WHERE status='OPEN'
    """)
    open_plates = {row["vehicle_plate"] for row in cur.fetchall()}

    cur.execute("""
        SELECT id, plate, caixa, active, created_at
        FROM vehicles
        ORDER BY plate ASC
    """)
    items = []
    for row in cur.fetchall():
        vehicle = dict(row)
        vehicle["status"] = vehicle_usage_status(vehicle, open_plates)
        items.append(vehicle)

    conn.close()
    return {"items": items}


@app.post("/api/admin/vehicles")
def admin_create_vehicle(
    plate: str = Form(...),
    description: str = Form(""),
    caixa: Optional[str] = Form(None),
    _=Depends(require_admin),
):
    full_plate = build_vehicle_plate(plate, description)
    caixa_value = parse_caixa_value(caixa)

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, active, created_at FROM vehicles WHERE plate=?", (full_plate,))
    existing = cur.fetchone()
    if existing:
        if int(existing["active"]) == 1:
            conn.close()
            raise HTTPException(status_code=409, detail="Este veículo já está cadastrado.")

        vehicle_id = existing["id"]
        cur.execute("""
            UPDATE vehicles
            SET active=1, caixa=?
            WHERE id=?
        """, (caixa_value, vehicle_id))
        conn.commit()
        conn.close()

        return {
            "ok": True,
            "vehicle": {
                "id": vehicle_id,
                "plate": full_plate,
                "caixa": caixa_value,
                "active": 1,
                "created_at": existing["created_at"],
                "status": "AVAILABLE",
            },
            "message": f"Veículo {full_plate} reativado com sucesso.",
        }

    now = datetime.now(timezone.utc).isoformat()
    vehicle_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO vehicles (id, plate, caixa, active, created_at)
        VALUES (?, ?, ?, 1, ?)
    """, (vehicle_id, full_plate, caixa_value, now))
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "vehicle": {
            "id": vehicle_id,
            "plate": full_plate,
            "caixa": caixa_value,
            "active": 1,
            "created_at": now,
            "status": "AVAILABLE",
        },
        "message": f"Veículo {full_plate} cadastrado com sucesso.",
    }


@app.put("/api/admin/vehicles/{vehicle_id}")
def admin_update_vehicle(
    vehicle_id: str,
    plate: str = Form(...),
    description: str = Form(""),
    caixa: Optional[str] = Form(None),
    _=Depends(require_admin),
):
    full_plate = build_vehicle_plate(plate, description)
    caixa_value = parse_caixa_value(caixa)

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, plate, active FROM vehicles WHERE id=?", (vehicle_id,))
    current = cur.fetchone()
    if not current:
        conn.close()
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")

    if int(current["active"]) != 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Veículo inativo.")

    old_plate = current["plate"]
    if full_plate != old_plate:
        cur.execute("SELECT id FROM vehicles WHERE plate=? AND id<>?", (full_plate, vehicle_id))
        if cur.fetchone():
            conn.close()
            raise HTTPException(status_code=409, detail="Já existe outro veículo com esta placa.")

    cur.execute("""
        UPDATE vehicles
        SET plate=?, caixa=?
        WHERE id=?
    """, (full_plate, caixa_value, vehicle_id))

    if full_plate != old_plate:
        cur.execute("""
            UPDATE assignments
            SET vehicle_plate=?
            WHERE vehicle_plate=?
        """, (full_plate, old_plate))

    cur.execute("""
        SELECT vehicle_plate
        FROM assignments
        WHERE status='OPEN'
    """)
    open_plates = {row["vehicle_plate"] for row in cur.fetchall()}

    cur.execute("""
        SELECT id, plate, caixa, active, created_at
        FROM vehicles
        WHERE id=?
    """, (vehicle_id,))
    updated = dict(cur.fetchone())
    updated["status"] = vehicle_usage_status(updated, open_plates)

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "vehicle": updated,
        "message": f"Veículo atualizado para {full_plate}.",
    }


@app.delete("/api/admin/vehicles/{vehicle_id}")
def admin_deactivate_vehicle(vehicle_id: str, _=Depends(require_admin)):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, plate, active FROM vehicles WHERE id=?", (vehicle_id,))
    current = cur.fetchone()
    if not current:
        conn.close()
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")

    if int(current["active"]) != 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Veículo já está inativo.")

    cur.execute("""
        SELECT id
        FROM assignments
        WHERE status='OPEN' AND vehicle_plate=?
        LIMIT 1
    """, (current["plate"],))
    if cur.fetchone():
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Não é possível desativar um veículo que está em uso no momento.",
        )

    cur.execute("UPDATE vehicles SET active=0 WHERE id=?", (vehicle_id,))
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "message": f"Veículo {current['plate']} desativado com sucesso.",
    }


@app.post("/api/admin/vehicles/{vehicle_id}/activate")
def admin_activate_vehicle(vehicle_id: str, _=Depends(require_admin)):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, plate, active, caixa, created_at FROM vehicles WHERE id=?", (vehicle_id,))
    current = cur.fetchone()
    if not current:
        conn.close()
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")

    if int(current["active"]) == 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Veículo já está ativo.")

    cur.execute("""
        SELECT id
        FROM vehicles
        WHERE plate=? AND active=1 AND id<>?
        LIMIT 1
    """, (current["plate"], vehicle_id))
    if cur.fetchone():
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Já existe outro veículo ativo com esta placa.",
        )

    cur.execute("UPDATE vehicles SET active=1 WHERE id=?", (vehicle_id,))
    vehicle = dict(current)
    vehicle["active"] = 1
    vehicle["status"] = "AVAILABLE"

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "vehicle": vehicle,
        "message": f"Veículo {current['plate']} reativado com sucesso.",
    }


@app.get("/api/admin/assignments")
def admin_list_assignments(limit: int = Query(200, ge=1, le=500), _=Depends(require_admin)):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, vehicle_plate, status, checkout_at, checkin_at, checkout_user, checkin_user
        FROM assignments
        ORDER BY checkout_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"items": rows}


@app.get("/api/admin/assignment/{assignment_id}")
def admin_assignment_details(assignment_id: str, _=Depends(require_admin)):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,))
    a = cur.fetchone()
    if not a:
        conn.close()
        raise HTTPException(status_code=404, detail="Não encontrado.")

    assignment = dict(a)

    try:
        assignment["checkout_answers_obj"] = json.loads(assignment.get("checkout_answers") or "{}")
    except Exception:
        assignment["checkout_answers_obj"] = {}

    try:
        assignment["checkin_answers_obj"] = json.loads(assignment.get("checkin_answers") or "{}")
    except Exception:
        assignment["checkin_answers_obj"] = {}

    cur.execute("""
        SELECT phase, slot, path, created_at
        FROM photos
        WHERE assignment_id=?
        ORDER BY created_at ASC
    """, (assignment_id,))
    photos = []
    for r in cur.fetchall():
        d = dict(r)
        filename = os.path.basename(d["path"])
        d["url"] = f"/uploads/{filename}"
        photos.append(d)

    conn.close()
    return {"assignment": assignment, "photos": photos}
