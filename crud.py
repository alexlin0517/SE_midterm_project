"""
資料存取與業務邏輯模組 (crud.py)
職責：封裝所有針對 PostgreSQL 資料庫的新增 (Create)、查詢 (Read)、更新 (Update)、刪除 (Delete) 操作。
嚴禁在 API 路由層直接執行資料庫查詢或修改，維持分層架構 (Layered Architecture) 的高凝聚力與低耦合度。
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from models import Manuscript, ManuscriptStatus


def create_manuscript(db: Session, title: str, content: str, author_id: int) -> Manuscript:
    """
    建立新稿件。
    依業務規則：新增稿件狀態預設為「編輯中」(Draft)。
    """
    new_manuscript = Manuscript(
        title=title,
        content=content,
        author_id=author_id,
        status=ManuscriptStatus.DRAFT.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_manuscript)
    db.commit()
    db.refresh(new_manuscript)
    return new_manuscript


def get_manuscript_by_id(db: Session, manuscript_id: int) -> Optional[Manuscript]:
    """
    透過稿件 ID 查詢單筆稿件。
    """
    return db.query(Manuscript).filter(Manuscript.id == manuscript_id).first()


def get_manuscripts_by_author(db: Session, author_id: int) -> List[Manuscript]:
    """
    查詢特定作者的所有稿件清單（依 ID 遞減排序，最新的在前）。
    """
    return (
        db.query(Manuscript)
        .filter(Manuscript.author_id == author_id)
        .order_by(Manuscript.id.desc())
        .all()
    )


def get_manuscripts_by_status(db: Session, status: str) -> List[Manuscript]:
    """
    依稿件狀態查詢（例如：供編輯儀表板查詢所有「審查中」的稿件）。
    """
    return (
        db.query(Manuscript)
        .filter(Manuscript.status == status)
        .order_by(Manuscript.id.asc())
        .all()
    )


def get_all_manuscripts(db: Session) -> List[Manuscript]:
    """
    查詢全系統所有稿件（供編輯檢視整體審查歷史與統計）。
    """
    return db.query(Manuscript).order_by(Manuscript.id.desc()).all()


def update_manuscript_content(db: Session, manuscript: Manuscript, title: str, content: str) -> Manuscript:
    """
    更新稿件標題與內文。
    依業務規則：編輯後狀態維持為「編輯中」(Draft)，並更新修改時間。
    """
    manuscript.title = title
    manuscript.content = content
    manuscript.status = ManuscriptStatus.DRAFT.value
    manuscript.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(manuscript)
    return manuscript


def update_manuscript_status(db: Session, manuscript: Manuscript, new_status: str) -> Manuscript:
    """
    變更稿件狀態 (State Transition)。
    可用於：送出審查 (Draft -> Under Review)、審核通過 (Under Review -> Approved)、退回 (Under Review -> Draft)。
    """
    manuscript.status = new_status
    manuscript.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(manuscript)
    return manuscript


def delete_manuscript(db: Session, manuscript: Manuscript) -> None:
    """
    刪除稿件。
    """
    db.delete(manuscript)
    db.commit()
