from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from backend.core.database import get_db
from backend.core.models import User, WikiRule
from backend.core.auth import get_current_user
from backend.core.limiter import limiter

router = APIRouter(tags=["Wiki Rules"])

# Pydantic sheme za unos i prikaz podataka
class WikiRuleCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = "general"
    is_global: Optional[bool] = False

class WikiRuleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    is_global: Optional[bool] = None

class WikiRuleResponse(BaseModel):
    id: str
    user_id: str
    title: str
    content: str
    category: str
    is_global: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/api/v1/wiki/rules", response_model=WikiRuleResponse)
@limiter.limit("15/minute")
def create_wiki_rule(
    request: Request,
    data: WikiRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Kreira novo Wiki pravilo za ulogovanog korisnika.
    """
    new_rule = WikiRule(
        user_id=current_user.id,
        title=data.title,
        content=data.content,
        category=data.category,
        is_global=data.is_global if current_user.is_admin else False # Samo admini mogu kreirati globalna pravila
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule


@router.get("/api/v1/wiki/rules", response_model=List[WikiRuleResponse])
def list_wiki_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Vraća sva Wiki pravila dostupna korisniku (njegova lokalna + globalna pravila).
    """
    rules = db.query(WikiRule).filter(
        (WikiRule.user_id == current_user.id) | (WikiRule.is_global == True)
    ).order_by(WikiRule.created_at.desc()).all()
    return rules


@router.put("/api/v1/wiki/rule/{rule_id}", response_model=WikiRuleResponse)
def update_wiki_rule(
    rule_id: str,
    data: WikiRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ažurira postojeće Wiki pravilo korisnika.
    """
    rule = db.query(WikiRule).filter(WikiRule.id == rule_id, WikiRule.user_id == current_user.id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Wiki pravilo nije pronađeno ili nemate pravo pristupa.")
        
    if data.title is not None:
        rule.title = data.title
    if data.content is not None:
        rule.content = data.content
    if data.category is not None:
        rule.category = data.category
    if data.is_global is not None and current_user.is_admin:
        rule.is_global = data.is_global
        
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/api/v1/wiki/rule/{rule_id}")
def delete_wiki_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Briše Wiki pravilo korisnika.
    """
    rule = db.query(WikiRule).filter(WikiRule.id == rule_id, WikiRule.user_id == current_user.id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Wiki pravilo nije pronađeno ili nemate pravo pristupa.")
        
    db.delete(rule)
    db.commit()
    return {"status": "success", "message": "Wiki pravilo je uspešno obrisano."}
