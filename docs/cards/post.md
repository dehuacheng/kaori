# Card: Post

## Identity

| Field | Value |
|-------|-------|
| Card Type | `post` |
| CardType Enum | `CardType.POST` |

## Purpose

Personal microblog for quick thoughts with optional photo attachments. Like a private Twitter — user writes free-form text posts that appear as cards in the feed on their date.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | Yes |
| Tap → detail | Yes (edit/view full content) |
| Swipe actions | Delete |
| Sort priority | 99 (chronological) |
| Pinned | No |

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `posts` | User posts (date, title, content, photo_path, photo_paths, is_pinned). Free-form markdown/text with optional photos. |

### API Endpoints

- `GET /api/post?date=...` — list posts by date (or recent history if no date)
- `POST /api/post` — create post (multipart: photos + fields {post_date, title, content})
- `GET /api/post/{id}` — get single post
- `PUT /api/post/{id}` — update {title, content, is_pinned}
- `DELETE /api/post/{id}` — delete

### Feed Loader

`_load_posts` in `feed_service.py` — fetches via `post_repo.list_by_date()`.

## Key Backend Files

- `models/post.py` — PostCreate, PostUpdate
- `storage/post_repo.py` — CRUD + list_by_date + get_history
- `services/post_service.py` — thin CRUD passthrough
- `api/post.py` — REST endpoints
