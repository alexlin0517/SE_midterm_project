"""
資料庫 ORM 模型定義模組 (models.py)
職責：定義系統核心實體模型，包含使用者 (User) 與稿件 (Manuscript)，以及稿件狀態與類別常數。
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from db import Base

# 預設稿件類別（當未選取類別或舊版資料庫無此欄位時使用）
DEFAULT_CATEGORY = "--無類別--"

# 系統提供之稿件類別清單
MANUSCRIPT_CATEGORIES = [
    "散文",
    "小說",
    "心得",
    "紀錄",
    "評論",
    "其他",
]


class ManuscriptStatus(str, enum.Enum):
    """
    稿件狀態列舉 (Status)
    - 編輯中 (Draft)：作者可自由編輯、刪除或送出審查
    - 審查中 (Under Review)：已送交編輯審查，鎖定編輯與刪除
    - 已通過 (Approved)：編輯審查通過，稿件流程完成
    """
    DRAFT = "編輯中"
    UNDER_REVIEW = "審查中"
    APPROVED = "已通過"


class User(Base):
    """
    使用者模型 (User)
    作為未來身分認證 (Authentication) 與 RBAC 權限擴充準備。
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    role = Column(String(20), nullable=False)  # 'author' 或 'editor'
    created_at = Column(DateTime, default=datetime.utcnow)


class Manuscript(Base):
    """
    稿件模型 (Manuscript)
    記錄投稿文章內容、類別與審查狀態生命週期。
    """
    __tablename__ = "manuscripts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(
        String(50),
        nullable=False,
        default=DEFAULT_CATEGORY,
        server_default=DEFAULT_CATEGORY
    )
    content = Column(Text, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default=ManuscriptStatus.DRAFT.value,
        index=True
    )
    author_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
