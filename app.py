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


# >>> TROQUE pelas suas 2 placas <<<
PLATES = ["AAA1A11/PORTARIA", "BBB2B22/MANUTENÇÃO"]

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
    if vehicle_plate not in PLATES:
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
    if not caixa:
        raise HTTPException(status_code=400, detail="Caixa não configurada para esta placa.")

    ok = abrir_caixa(caixa)
    if not ok:
        raise HTTPException(status_code=502, detail=f"Não foi possível acionar a fechadura da caixa {caixa}.")

    return {"ok": True, "caixa": caixa, "message": f"Fechadura da caixa {caixa} acionada."}


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


def definir_caixa(plate):
    if str(plate).startswith("AAA1A11"):
        return 1
    elif str(plate).startswith("BBB2B22"):
        return 2
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
        checkin_answers TEXT
    )
    """)

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

    conn.commit()
    conn.close()


init_db()


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
    for p in PLATES:
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
    if vehicle_plate not in PLATES:
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

    if not box_released:
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
