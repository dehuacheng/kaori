from datetime import date as date_mod
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from kaori.models.post import PostCreate, PostUpdate
from kaori.services import post_service
from kaori.services.photo_extraction_service import trigger_photo_extraction, _get_all_photo_paths
from kaori.storage.file_store import save_photo

router = APIRouter(prefix="/post", tags=["api-post"])

MEDIA_TYPE_MAP = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/heic": "image/jpeg",
    "image/heif": "image/jpeg",
}


@router.get("")
async def list_posts(date: str | None = None, limit: int = 50):
    if date:
        return await post_service.list_by_date(date)
    return await post_service.get_history(limit=limit)


@router.post("")
async def create_post(
    content: str = Form(...),
    post_date: str = Form(None),
    title: str = Form(None),
    photo: UploadFile | None = File(None),
    photos: Optional[list[UploadFile]] = File(None),
):
    today = post_date or date_mod.today().isoformat()
    photo_path = None
    photo_paths: list[str] = []

    # Handle multiple photos
    if photos:
        for p in photos:
            if p.size and p.size > 0:
                image_bytes = await p.read()
                media_type = MEDIA_TYPE_MAP.get(p.content_type, "image/jpeg")
                ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
                photo_paths.append(save_photo(image_bytes, ext))
        if photo_paths:
            photo_path = photo_paths[0]

    # Fall back to single photo field
    if not photo_paths and photo and photo.size and photo.size > 0:
        image_bytes = await photo.read()
        media_type = MEDIA_TYPE_MAP.get(photo.content_type, "image/jpeg")
        ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
        photo_path = save_photo(image_bytes, ext)
        photo_paths = [photo_path]

    post_id = await post_service.create(
        post_date=today, title=title, content=content,
        photo_path=photo_path, photo_paths=photo_paths or None,
    )

    # Auto-extract photo description in background
    if photo_paths:
        trigger_photo_extraction("posts", post_id, photo_paths)
    elif photo_path:
        trigger_photo_extraction("posts", post_id, [photo_path])

    return {"id": post_id, "date": today}


@router.get("/{post_id}")
async def get_post(post_id: int):
    post = await post_service.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/{post_id}")
async def update_post(post_id: int, body: PostUpdate):
    await post_service.update(
        post_id, title=body.title, content=body.content, is_pinned=body.is_pinned,
    )
    return {"id": post_id}


@router.post("/{post_id}/parse-photos")
async def parse_post_photos(post_id: int):
    """Trigger photo description extraction for a post."""
    post = await post_service.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    paths = _get_all_photo_paths(post)
    if not paths:
        raise HTTPException(status_code=400, detail="Post has no photos")
    # Clear existing description so UI can show "processing" state
    from kaori.database import get_db
    db = await get_db()
    try:
        await db.execute(
            "UPDATE posts SET photo_description = NULL WHERE id = ?", (post_id,),
        )
        await db.commit()
    finally:
        await db.close()
    trigger_photo_extraction("posts", post_id, paths)
    return {"id": post_id, "status": "processing"}


@router.delete("/{post_id}")
async def delete_post(post_id: int):
    deleted = await post_service.delete(post_id)
    return {"id": post_id, "deleted": deleted}
