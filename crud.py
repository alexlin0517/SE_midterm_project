"""
資料存取與業務邏輯模組 (crud.py)
職責：封裝所有針對 PostgreSQL 資料庫的新增 (Create)、查詢 (Read)、更新 (Update)、刪除 (Delete) 操作，
      並確保舊版資料庫（缺少 category 欄位時）的自動相容與降級處理。
嚴禁在 API 路由層直接執行資料庫查詢或修改，維持分層架構 (Layered Architecture) 的高凝聚力與低耦合度。
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from models import Manuscript, ManuscriptStatus, DEFAULT_CATEGORY

_category_column_checked = False
_category_column_exists = False


def normalize_category(category: Optional[str]) -> str:
    """
    正規化稿件類別：
    若未選取、傳入空值或 '--無類別--'，統一回傳 '--無類別--'。
    """
    if category is None:
        return DEFAULT_CATEGORY
    cleaned = category.strip()
    if not cleaned or cleaned == DEFAULT_CATEGORY:
        return DEFAULT_CATEGORY
    return cleaned[:50]


def ensure_schema_compatibility(bind) -> bool:
    """
    檢查並確保 manuscripts 資料表具備 category 欄位（舊版資料庫相容處理）。
    - 若資料表已存在但缺少 category 欄位，自動補齊欄位並設預設值為 '--無類別--'。
    - 若資料庫權限受限無法執行 ALTER TABLE，回傳 False 並由存取層自動以 '--無類別--' 相容運行。
    """
    global _category_column_checked, _category_column_exists
    if _category_column_checked:
        return _category_column_exists

    try:
        inspector = inspect(bind)
        if not inspector.has_table("manuscripts"):
            return False

        columns = [col["name"] for col in inspector.get_columns("manuscripts")]
        if "category" not in columns:
            with bind.begin() as conn:
                if bind.dialect.name == "postgresql":
                    conn.execute(
                        text(
                            "ALTER TABLE manuscripts "
                            f"ADD COLUMN IF NOT EXISTS category VARCHAR(50) NOT NULL DEFAULT '{DEFAULT_CATEGORY}'"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE manuscripts "
                            f"ADD COLUMN category VARCHAR(50) NOT NULL DEFAULT '{DEFAULT_CATEGORY}'"
                        )
                    )
                conn.execute(
                    text(
                        "UPDATE manuscripts SET category = :default_cat "
                        "WHERE category IS NULL OR category = ''"
                    ),
                    {"default_cat": DEFAULT_CATEGORY}
                )

        _category_column_checked = True
        _category_column_exists = True
        return True
    except Exception as exc:
        print(f">>> 【提醒】舊版資料庫尚未含 category 欄位且無法自動升級，將以預設類別「{DEFAULT_CATEGORY}」相容模式執行: {exc}")
        _category_column_checked = True
        _category_column_exists = False
        return False


def _row_to_legacy_manuscript(row) -> Manuscript:
    """
    將舊版資料庫查詢結果（無 category 欄位）轉換為 Manuscript 物件，類別預設為 '--無類別--'。
    """
    return Manuscript(
        id=row.id,
        title=row.title,
        category=DEFAULT_CATEGORY,
        content=row.content,
        status=row.status,
        author_id=row.author_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _normalize_orm_category(manuscript: Optional[Manuscript]) -> Optional[Manuscript]:
    if manuscript is not None and (not manuscript.category or not manuscript.category.strip()):
        manuscript.category = DEFAULT_CATEGORY
    return manuscript


def create_manuscript(
    db: Session,
    title: str,
    content: str,
    author_id: int,
    category: Optional[str] = None
) -> Manuscript:
    """
    建立新稿件。
    依業務規則：新增稿件狀態預設為「編輯中」(Draft)；
    若未選取類別或舊版資料庫無此欄位，一律以 '--無類別--' 提交。
    """
    now = datetime.utcnow()
    has_category = ensure_schema_compatibility(db.get_bind())
    resolved_category = normalize_category(category)

    if has_category:
        new_manuscript = Manuscript(
            title=title,
            category=resolved_category,
            content=content,
            author_id=author_id,
            status=ManuscriptStatus.DRAFT.value,
            created_at=now,
            updated_at=now
        )
        db.add(new_manuscript)
        db.commit()
        db.refresh(new_manuscript)
        return new_manuscript

    # 舊版資料庫無 category 欄位時的相容寫入，回傳類別統一為 '--無類別--'
    result = db.execute(
        text(
            "INSERT INTO manuscripts (title, content, status, author_id, created_at, updated_at) "
            "VALUES (:title, :content, :status, :author_id, :created_at, :updated_at) "
            "RETURNING id"
        ),
        {
            "title": title,
            "content": content,
            "status": ManuscriptStatus.DRAFT.value,
            "author_id": author_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    new_id = result.scalar_one()
    db.commit()
    return Manuscript(
        id=new_id,
        title=title,
        category=DEFAULT_CATEGORY,
        content=content,
        status=ManuscriptStatus.DRAFT.value,
        author_id=author_id,
        created_at=now,
        updated_at=now,
    )


def get_manuscript_by_id(db: Session, manuscript_id: int) -> Optional[Manuscript]:
    """
    透過稿件 ID 查詢單筆稿件。
    """
    if ensure_schema_compatibility(db.get_bind()):
        manuscript = db.query(Manuscript).filter(Manuscript.id == manuscript_id).first()
        return _normalize_orm_category(manuscript)

    row = db.execute(
        text(
            "SELECT id, title, content, status, author_id, created_at, updated_at "
            "FROM manuscripts WHERE id = :id"
        ),
        {"id": manuscript_id}
    ).first()
    return _row_to_legacy_manuscript(row) if row else None


def get_manuscripts_by_author(db: Session, author_id: int) -> List[Manuscript]:
    """
    查詢特定作者的所有稿件清單（依 ID 遞減排序，最新的在前）。
    """
    if ensure_schema_compatibility(db.get_bind()):
        items = (
            db.query(Manuscript)
            .filter(Manuscript.author_id == author_id)
            .order_by(Manuscript.id.desc())
            .all()
        )
        return [_normalize_orm_category(item) for item in items]

    rows = db.execute(
        text(
            "SELECT id, title, content, status, author_id, created_at, updated_at "
            "FROM manuscripts WHERE author_id = :author_id ORDER BY id DESC"
        ),
        {"author_id": author_id}
    ).all()
    return [_row_to_legacy_manuscript(row) for row in rows]


def get_manuscripts_by_status(db: Session, status: str) -> List[Manuscript]:
    """
    依稿件狀態查詢（例如：供編輯儀表板查詢所有「審查中」的稿件）。
    """
    if ensure_schema_compatibility(db.get_bind()):
        items = (
            db.query(Manuscript)
            .filter(Manuscript.status == status)
            .order_by(Manuscript.id.asc())
            .all()
        )
        return [_normalize_orm_category(item) for item in items]

    rows = db.execute(
        text(
            "SELECT id, title, content, status, author_id, created_at, updated_at "
            "FROM manuscripts WHERE status = :status ORDER BY id ASC"
        ),
        {"status": status}
    ).all()
    return [_row_to_legacy_manuscript(row) for row in rows]


def get_all_manuscripts(db: Session) -> List[Manuscript]:
    """
    查詢全系統所有稿件（供編輯檢視整體審查歷史與統計）。
    """
    if ensure_schema_compatibility(db.get_bind()):
        items = db.query(Manuscript).order_by(Manuscript.id.desc()).all()
        return [_normalize_orm_category(item) for item in items]

    rows = db.execute(
        text(
            "SELECT id, title, content, status, author_id, created_at, updated_at "
            "FROM manuscripts ORDER BY id DESC"
        )
    ).all()
    return [_row_to_legacy_manuscript(row) for row in rows]


def update_manuscript_content(
    db: Session,
    manuscript: Manuscript,
    title: str,
    content: str,
    category: Optional[str] = None
) -> Manuscript:
    """
    更新稿件標題、類別與內文。
    依業務規則：編輯後狀態維持為「編輯中」(Draft)，並更新修改時間；
    若未選取類別或舊版資料庫無此欄位，以 '--無類別--' 提交。
    """
    now = datetime.utcnow()
    has_category = ensure_schema_compatibility(db.get_bind())
    resolved_category = normalize_category(category)

    if has_category:
        manuscript.title = title
        manuscript.category = resolved_category
        manuscript.content = content
        manuscript.status = ManuscriptStatus.DRAFT.value
        manuscript.updated_at = now
        db.commit()
        db.refresh(manuscript)
        return manuscript

    db.execute(
        text(
            "UPDATE manuscripts "
            "SET title = :title, content = :content, status = :status, updated_at = :updated_at "
            "WHERE id = :id"
        ),
        {
            "id": manuscript.id,
            "title": title,
            "content": content,
            "status": ManuscriptStatus.DRAFT.value,
            "updated_at": now,
        }
    )
    db.commit()
    manuscript.title = title
    manuscript.category = DEFAULT_CATEGORY
    manuscript.content = content
    manuscript.status = ManuscriptStatus.DRAFT.value
    manuscript.updated_at = now
    return manuscript


def update_manuscript_status(db: Session, manuscript: Manuscript, new_status: str) -> Manuscript:
    """
    變更稿件狀態 (State Transition)。
    可用於：送出審查 (Draft -> Under Review)、審核通過 (Under Review -> Approved)、退回 (Under Review -> Draft)。
    """
    now = datetime.utcnow()
    if ensure_schema_compatibility(db.get_bind()):
        manuscript.status = new_status
        manuscript.updated_at = now
        db.commit()
        db.refresh(manuscript)
        return manuscript

    db.execute(
        text(
            "UPDATE manuscripts SET status = :status, updated_at = :updated_at WHERE id = :id"
        ),
        {"id": manuscript.id, "status": new_status, "updated_at": now}
    )
    db.commit()
    manuscript.status = new_status
    manuscript.updated_at = now
    return manuscript


def delete_manuscript(db: Session, manuscript: Manuscript) -> None:
    """
    刪除稿件。
    """
    if ensure_schema_compatibility(db.get_bind()):
        db.delete(manuscript)
        db.commit()
        return

    db.execute(
        text("DELETE FROM manuscripts WHERE id = :id"),
        {"id": manuscript.id}
    )
    db.commit()
