import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import jwt as pyjwt

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.models import User, Waitlist
from backend.core.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    oauth2_scheme
)
from backend.core.schemas import UserRegisterRequest, UserLoginRequest, WaitlistRequest
from backend.core.limiter import limiter
from backend.services.redis import get_redis_client

router = APIRouter(tags=["Auth"])

@router.post("/api/v1/waitlist")
@limiter.limit("5/minute")
def add_to_waitlist(request: Request, data: WaitlistRequest, db: Session = Depends(get_db)):
    """
    Dodavanje korisnika na listu čekanja (Waitlist) za zatvorenu betu.
    """
    email_clean = data.email.strip().lower()
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email_clean):
        raise HTTPException(status_code=400, detail="Neispravan format email adrese.")
        
    existing_waitlist = db.query(Waitlist).filter(Waitlist.email == email_clean).first()
    if existing_waitlist:
        raise HTTPException(status_code=400, detail="Ovaj email je već prijavljen na listu čekanja.")
        
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Korisnik sa ovim email-om već ima otvoren nalog. Prijavite se.")
        
    new_entry = Waitlist(email=email_clean)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    return {"status": "success", "message": "Uspešno ste se prijavili na listu čekanja."}


@router.post("/api/v1/auth/register")
@limiter.limit("10/minute")
def register_user(request: Request, data: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Registracija novog korisničkog naloga.
    """
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Korisnik sa ovim email-om već postoji.")
    
    hashed_pwd = get_password_hash(data.password)
    new_user = User(email=data.email, password_hash=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "message": "Nalog je uspešno kreiran. Prijavite se."}

@router.post("/api/v1/auth/login")
@limiter.limit("15/minute")
def login_user(request: Request, data: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Prijava korisnika i generisanje JWT tokena.
    """
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Pogrešan email ili lozinka.")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "is_admin": getattr(user, "is_admin", False)
        }
    }

@router.get("/api/v1/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Profil ulogovanog korisnika na osnovu JWT tokena.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_admin": getattr(current_user, "is_admin", False)
    }

@router.post("/api/v1/auth/logout")
def logout(token: str = Depends(oauth2_scheme), current_user: User = Depends(get_current_user)):
    """
    Dodaje trenutni JWT token u blocklistu u Redisu do isteka njegovog važenja.
    """
    if not token:
        return {"status": "success"}
    try:
        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        exp = payload.get("exp")
        if exp:
            now = datetime.utcnow().timestamp()
            ttl = int(exp - now)
            if ttl > 0:
                r = get_redis_client()
                r.setex(f"token_blocklist:{token}", ttl, "revoked")
    except Exception:
        pass
    return {"status": "success", "message": "Uspešno ste se odjavili."}
