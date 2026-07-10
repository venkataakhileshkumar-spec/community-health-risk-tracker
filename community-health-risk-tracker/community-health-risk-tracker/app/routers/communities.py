"""
CRUD endpoints for communities.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/communities", tags=["communities"])


@router.post("", response_model=schemas.CommunityOut, status_code=201)
def create_community(payload: schemas.CommunityCreate, db: Session = Depends(get_db)):
    community = models.Community(**payload.model_dump())
    db.add(community)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Community '{payload.name}, {payload.state}' already exists.",
        )
    db.refresh(community)
    return community


@router.get("", response_model=List[schemas.CommunityOut])
def list_communities(
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    db: Session = Depends(get_db),
):
    query = db.query(models.Community)
    if state:
        query = query.filter(models.Community.state == state.upper())
    return query.order_by(models.Community.name).all()


@router.get("/{community_id}", response_model=schemas.CommunityOut)
def get_community(community_id: int, db: Session = Depends(get_db)):
    community = db.query(models.Community).get(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return community


@router.delete("/{community_id}", status_code=204)
def delete_community(community_id: int, db: Session = Depends(get_db)):
    community = db.query(models.Community).get(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    db.delete(community)
    db.commit()
    return None
