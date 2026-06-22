import jwt as pyjwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session
import redis.asyncio as aioredis
import json
import asyncio

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.models import User, Project

router = APIRouter(tags=["WebSocket"])

async def get_ws_user(token: str, db: Session) -> User:
    """
    Pomocna funkcija za verifikaciju JWT tokena iz query parametra u WebSocket-u.
    """
    if not token:
        return None
    
    # Provera Redis blockliste
    try:
        # Koristimo sinhroni redis klijent za brzu proveru blockliste jer se izvrsava na pocetku konekcije
        from backend.services.redis import get_redis_client
        r = get_redis_client()
        if r.exists(f"token_blocklist:{token}"):
            return None
    except Exception:
        pass
        
    try:
        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except pyjwt.PyJWTError:
        return None
        
    user = db.query(User).filter(User.id == user_id).first()
    return user

@router.websocket("/api/v1/ws/project/{project_id}")
async def project_progress_ws(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    await websocket.accept()
    
    # Verifikacija korisnika
    user = await get_ws_user(token, db)
    if not user:
        await websocket.close(code=4008) # WS_1008_POLICY_VIOLATION
        return
        
    # Provera prava pristupa projektu
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        await websocket.close(code=4008)
        return
        
    # Povezivanje na Redis Pub/Sub asinhrono
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    channel_name = f"project:{project_id}:progress"
    
    try:
        await pubsub.subscribe(channel_name)
        print(f"[WS SUCCESS] Korisnik {user.email} se pretplatio na kanal {channel_name}", flush=True)
        
        # Slanje inicijalne poruke
        await websocket.send_text(json.dumps({
            "status": "connected",
            "message": f"Pretplata na progres projekta {project_id} uspešna."
        }))
        
        # Petlja za osluškivanje Redis Pub/Sub poruka i slanje klijentu
        while True:
            try:
                # Osluškujemo poruku sa timeout-om da bismo dozvolili detekciju prekida konekcije sa klijentske strane
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    data = message.get("data")
                    await websocket.send_text(data)
            except asyncio.TimeoutError:
                # Samo nastavljamo petlju ako nema novih poruka u poslednjoj sekundi
                pass
            except WebSocketDisconnect:
                # Hvata prekid konekcije tokom slanja
                raise
            except Exception as e:
                print(f"[WS ERROR] Greška u Pub/Sub čitanju: {e}", flush=True)
                break
                
            # Provera da li je klijent zatvorio vezu (kroz primanje ping-a/poruka sa klijenta ako ih ima)
            # websocket.receive_text() je blokirajući poziv, pa koristimo asyncio.wait_for da ne blokiramo slanje
            try:
                # Ako klijent pošalje bilo šta (npr. ping/odgovor), samo pročitamo i odbacimo
                await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                raise
            
    except WebSocketDisconnect:
        print(f"[WS DISCONNECT] Korisnik {user.email} je prekinuo WebSocket vezu.", flush=True)
    finally:
        # Čišćenje resursa
        try:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await redis_client.close()
        except Exception as clean_err:
            print(f"[WS CLEANUP ERROR] Greška pri čišćenju resursa: {clean_err}", flush=True)
