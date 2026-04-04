from fastapi import APIRouter, HTTPException

from kaori.models.post import PostCreate, PostUpdate
from kaori.services import post_service

router = APIRouter(prefix="/post", tags=["api-post"])


@router.get("")
async def list_posts(date: str | None = None, limit: int = 50):
    if date:
        return await post_service.list_by_date(date)
    return await post_service.get_history(limit=limit)


@router.post("")
async def create_post(body: PostCreate):
    post_id = await post_service.create(
        post_date=body.date, title=body.title, content=body.content,
    )
    return {"id": post_id, "date": body.date}


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


@router.delete("/{post_id}")
async def delete_post(post_id: int):
    deleted = await post_service.delete(post_id)
    return {"id": post_id, "deleted": deleted}
