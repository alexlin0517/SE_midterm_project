"""
主應用程式與路由模組 (main.py)
職責：FastAPI 實例建立、Jinja2 模板設定、MVC 控制器 (Controller) 路由定義、
      參數驗證、狀態轉換檢查與 HTTP 錯誤處理。
"""

from contextlib import asynccontextmanager
from typing import Optional
import jinja2
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session

import db
import models
import crud
from models import ManuscriptStatus, MANUSCRIPT_CATEGORIES, DEFAULT_CATEGORY


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    生命週期管理 (Lifespan Context Manager)
    在應用程式啟動時嘗試自動建立資料表結構，並檢查舊版資料庫欄位相容性。
    """
    try:
        models.Base.metadata.create_all(bind=db.engine)
        crud.ensure_schema_compatibility(db.engine)
        print(">>> 資料庫連線正常，已確認資料表 (manuscripts, users) 建立與結構相容就緒。")
    except Exception as exc:
        print(f">>> 【提醒】資料庫初始化失敗，請檢查 db.py 連線設定: {exc}")
    yield


app = FastAPI(
    title="投稿審查系統",
    description="基於 FastAPI + SQLAlchemy + PostgreSQL + Jinja2 的單體式伺服器端渲染 (SSR) 投稿審查系統",
    lifespan=lifespan
)

# 掛載靜態資源目錄 (CSS、背景圖片、SVG 圖示等靜態檔案)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 設定 Jinja2 模板引擎 (同時支援 templates/ 與內嵌 static/icons/ 路徑)
_jinja_env = jinja2.Environment(
    loader=jinja2.ChoiceLoader([
        jinja2.FileSystemLoader("templates"),
        jinja2.PrefixLoader({
            "static": jinja2.PrefixLoader({
                "icons": jinja2.FileSystemLoader("static/icons"),
            }),
        }),
    ]),
    autoescape=jinja2.select_autoescape(),
)
templates = Jinja2Templates(env=_jinja_env)


# ==============================================================================
# 全域例外處理 (Exception Handlers)
# 確保發生非法狀態轉換或找不到資源時，回傳標準 HTTP 錯誤碼與友善的純 HTML 錯誤頁面
# ==============================================================================
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "status_code": exc.status_code,
            "detail": exc.detail
        },
        status_code=exc.status_code
    )


# ==============================================================================
# 1. 模擬登入首頁 (Index)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """
    模擬登入入口頁面：提供作者與編輯的角色切換連結
    """
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# ==============================================================================
# 2. 作者相關路由 (Author Routes)
# ==============================================================================
@app.get("/author/{author_id}/dashboard", response_class=HTMLResponse)
async def author_dashboard(
    request: Request,
    author_id: int,
    session: Session = Depends(db.get_db)
):
    """
    作者儀表板：檢視該作者擁有的所有稿件與其狀態
    """
    manuscripts = crud.get_manuscripts_by_author(session, author_id=author_id)
    return templates.TemplateResponse(
        request=request,
        name="author_dashboard.html",
        context={
            "author_id": author_id,
            "manuscripts": manuscripts
        }
    )


@app.get("/author/{author_id}/manuscripts/new", response_class=HTMLResponse)
async def new_manuscript_page(
    request: Request,
    author_id: int
):
    """
    新增稿件頁面：顯示純 HTML 表單
    """
    return templates.TemplateResponse(
        request=request,
        name="manuscript_form.html",
        context={
            "author_id": author_id,
            "manuscript": None,
            "categories": MANUSCRIPT_CATEGORIES,
            "default_category": DEFAULT_CATEGORY,
        }
    )


@app.post("/author/{author_id}/manuscripts/new")
async def create_manuscript_action(
    author_id: int,
    title: str = Form(...),
    content: str = Form(...),
    category: Optional[str] = Form(default=None),
    form_author_id: int = Form(..., alias="author_id"),
    session: Session = Depends(db.get_db)
):
    """
    處理作者新增稿件請求：
    [業務規則] 新增稿件 => 狀態初始化為「編輯中」；若未選取類別或舊版資料庫無此欄位，以「--無類別--」提交
    """
    if author_id != form_author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="路徑作者編號與表單作者編號不一致。"
        )

    crud.create_manuscript(
        db=session,
        title=title.strip(),
        content=content.strip(),
        author_id=author_id,
        category=category
    )

    # 303 See Other 重新導向回作者儀表板
    return RedirectResponse(
        url=f"/author/{author_id}/dashboard",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.get("/author/{author_id}/manuscripts/{manuscript_id}/edit", response_class=HTMLResponse)
async def edit_manuscript_page(
    request: Request,
    author_id: int,
    manuscript_id: int,
    session: Session = Depends(db.get_db)
):
    """
    編輯稿件頁面：
    [業務規則] 只有狀態為「編輯中」的稿件允許編輯
    """
    manuscript = crud.get_manuscript_by_id(session, manuscript_id)
    if not manuscript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {manuscript_id} 的稿件。"
        )

    if manuscript.author_id != author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足：您只能編輯自己撰寫的稿件。"
        )

    if manuscript.status != ManuscriptStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法操作：稿件當前狀態為「{manuscript.status}」，只有「編輯中」的稿件允許再次修改。"
        )

    return templates.TemplateResponse(
        request=request,
        name="manuscript_form.html",
        context={
            "author_id": author_id,
            "manuscript": manuscript,
            "categories": MANUSCRIPT_CATEGORIES,
            "default_category": DEFAULT_CATEGORY,
        }
    )


@app.post("/author/{author_id}/manuscripts/{manuscript_id}/edit")
async def update_manuscript_action(
    author_id: int,
    manuscript_id: int,
    title: str = Form(...),
    content: str = Form(...),
    category: Optional[str] = Form(default=None),
    form_author_id: int = Form(..., alias="author_id"),
    session: Session = Depends(db.get_db)
):
    """
    處理作者更新稿件請求：
    [業務規則] 編輯稿件 => 狀態保持為「編輯中」；若未選取類別或舊版資料庫無此欄位，以「--無類別--」提交
    """
    if author_id != form_author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="路徑作者編號與表單作者編號不一致。"
        )

    manuscript = crud.get_manuscript_by_id(session, manuscript_id)
    if not manuscript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {manuscript_id} 的稿件。"
        )

    if manuscript.author_id != author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足：您只能修改自己撰寫的稿件。"
        )

    if manuscript.status != ManuscriptStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法操作：稿件當前狀態為「{manuscript.status}」，無法在非「編輯中」狀態下更新。"
        )

    crud.update_manuscript_content(
        db=session,
        manuscript=manuscript,
        title=title.strip(),
        content=content.strip(),
        category=category
    )

    return RedirectResponse(
        url=f"/author/{author_id}/dashboard",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/author/{author_id}/manuscripts/{manuscript_id}/submit")
async def submit_manuscript_action(
    author_id: int,
    manuscript_id: int,
    form_author_id: int = Form(..., alias="author_id"),
    session: Session = Depends(db.get_db)
):
    """
    處理作者送出審查請求：
    [狀態流轉規則] [作者] 送出投稿 => 狀態從「編輯中」改為「審查中」
    """
    if author_id != form_author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="路徑作者編號與表單作者編號不一致。"
        )

    manuscript = crud.get_manuscript_by_id(session, manuscript_id)
    if not manuscript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {manuscript_id} 的稿件。"
        )

    if manuscript.author_id != author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足：您只能送審屬於自己的稿件。"
        )

    if manuscript.status != ManuscriptStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法狀態轉換：稿件狀態目前為「{manuscript.status}」，只有「編輯中」的稿件方能送出審查。"
        )

    crud.update_manuscript_status(session, manuscript, ManuscriptStatus.UNDER_REVIEW.value)

    return RedirectResponse(
        url=f"/author/{author_id}/dashboard",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/author/{author_id}/manuscripts/{manuscript_id}/delete")
async def delete_manuscript_action(
    author_id: int,
    manuscript_id: int,
    form_author_id: int = Form(..., alias="author_id"),
    session: Session = Depends(db.get_db)
):
    """
    處理作者刪除稿件請求：
    [狀態流轉規則] [作者] 刪除稿件 => 只能刪除「編輯中」的稿件
    """
    if author_id != form_author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="路徑作者編號與表單作者編號不一致。"
        )

    manuscript = crud.get_manuscript_by_id(session, manuscript_id)
    if not manuscript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {manuscript_id} 的稿件。"
        )

    if manuscript.author_id != author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足：您只能刪除屬於自己的稿件。"
        )

    if manuscript.status != ManuscriptStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法刪除操作：只能刪除「編輯中」的稿件，當前稿件狀態為「{manuscript.status}」。"
        )

    crud.delete_manuscript(session, manuscript)

    return RedirectResponse(
        url=f"/author/{author_id}/dashboard",
        status_code=status.HTTP_303_SEE_OTHER
    )


# ==============================================================================
# 3. 編輯相關路由 (Editor Routes)
# ==============================================================================
@app.get("/editor/dashboard", response_class=HTMLResponse)
async def editor_dashboard(
    request: Request,
    session: Session = Depends(db.get_db)
):
    """
    編輯儀表板：
    顯示所有「審查中」的稿件，並附上全系統稿件一覽紀錄
    """
    under_review_manuscripts = crud.get_manuscripts_by_status(
        session,
        status=ManuscriptStatus.UNDER_REVIEW.value
    )
    all_manuscripts = crud.get_all_manuscripts(session)

    return templates.TemplateResponse(
        request=request,
        name="editor_dashboard.html",
        context={
            "under_review_manuscripts": under_review_manuscripts,
            "all_manuscripts": all_manuscripts
        }
    )


@app.post("/editor/manuscripts/{manuscript_id}/approve")
async def approve_manuscript_action(
    manuscript_id: int,
    session: Session = Depends(db.get_db)
):
    """
    處理編輯審核通過請求：
    [狀態流轉規則] [編輯] 選擇通過 => 狀態從「審查中」改為「已通過」
    """
    manuscript = crud.get_manuscript_by_id(session, manuscript_id)
    if not manuscript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {manuscript_id} 的稿件。"
        )

    if manuscript.status != ManuscriptStatus.UNDER_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法狀態轉換：只有「審查中」的稿件才能進行審核通過，當前稿件狀態為「{manuscript.status}」。"
        )

    crud.update_manuscript_status(session, manuscript, ManuscriptStatus.APPROVED.value)

    return RedirectResponse(
        url="/editor/dashboard",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/editor/manuscripts/{manuscript_id}/reject")
async def reject_manuscript_action(
    manuscript_id: int,
    session: Session = Depends(db.get_db)
):
    """
    處理編輯退回稿件請求：
    [狀態流轉規則] [編輯] 退回稿件 => 狀態從「審查中」改為「編輯中」
    """
    manuscript = crud.get_manuscript_by_id(session, manuscript_id)
    if not manuscript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到編號為 {manuscript_id} 的稿件。"
        )

    if manuscript.status != ManuscriptStatus.UNDER_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法狀態轉換：只有「審查中」的稿件才能進行退回操作，當前稿件狀態為「{manuscript.status}」。"
        )

    crud.update_manuscript_status(session, manuscript, ManuscriptStatus.DRAFT.value)

    return RedirectResponse(
        url="/editor/dashboard",
        status_code=status.HTTP_303_SEE_OTHER
    )
