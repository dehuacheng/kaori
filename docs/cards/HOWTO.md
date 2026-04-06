# How to Add or Edit a Card

> Token-efficient guide for Claude Code. Read this instead of scanning the whole codebase.

## Two Categories of Feed Cards

Cards appear in the feed in two ways:

1. **Items-based** (meal, weight, workout, post, reminder) — come as entries in `FeedDateGroup.items[]` array. Each instance has its own `id`, `created_at`, and sort by time.
2. **Singleton** (nutrition, summary, portfolio, weather) — come as dedicated fields on `FeedDateGroup` (e.g., `group.nutrition_totals`, `group.summary`). One per date.

This affects how the feed loader and iOS `applyFeedResponse` work (see below).

---

## Adding a New Card Type

### Files to CREATE (4 backend + 2-4 iOS)

**Backend:**

| # | File | What to put |
|---|------|-------------|
| 1 | `kaori/models/xxx.py` | Pydantic models: `XxxCreate(BaseModel)`, `XxxUpdate(BaseModel)` |
| 2 | `kaori/storage/xxx_repo.py` | CRUD functions: `list_by_date(date_str)`, `get(id)`, `create(...)`, `update(id, ...)`, `delete(id)` |
| 3 | `kaori/services/xxx_service.py` | Thin passthrough calling repo. Add business logic here if needed. |
| 4 | `kaori/api/xxx.py` | `router = APIRouter(prefix="/xxx", tags=["api-xxx"])` with GET/POST/PUT/DELETE endpoints |

**iOS:**

| # | File | What to put |
|---|------|-------------|
| 1 | `KaoriApp/CardModule/Modules/XxxCardModule.swift` | Struct conforming to `CardModule` protocol |
| 2 | `KaoriApp/Views/Xxx/XxxFeedCard.swift` | Feed card SwiftUI view (MUST use `.feedCard()` modifier) |
| 3 | `KaoriApp/Views/Xxx/XxxDetailView.swift` | Detail view (if `hasFeedDetailView = true`) |
| 4 | `KaoriApp/Views/Xxx/XxxCreateView.swift` | Create view (if `supportsManualCreation = true`) |
| 5 | `KaoriApp/Views/Xxx/XxxListView.swift` | Data list view (if `hasDataListView = true`) |
| 6 | `KaoriApp/Models/Xxx.swift` | Codable model struct (if not reusing existing) |

### Files to EDIT (1-line additions each)

**Backend (5 files, ~1 line each):**

| # | File | Line to add |
|---|------|-------------|
| 1 | `kaori/models/card.py` | `XXX = "xxx"` in `CardType` enum |
| 2 | `kaori/services/feed_service.py` | Add `_load_xxx` function + `CardType.XXX: _load_xxx` in `CARD_LOADERS` dict |
| 3 | `kaori/storage/card_preference_repo.py` | `CardType.XXX: (True, False, 99)` in `_DEFAULTS` dict |
| 4 | `kaori/api/router.py` | `api_router.include_router(xxx.router)` |
| 5 | `kaori/database.py` | `CREATE TABLE IF NOT EXISTS` in SCHEMA string |

**iOS (4 files, ~1 line each):**

| # | File | Line to add |
|---|------|-------------|
| 1 | `KaoriApp.swift` | `registry.register(XxxCardModule())` in init |
| 2 | `KaoriApp/Models/FeedItem.swift` | `static func xxx(...)` factory method |
| 3 | `KaoriApp/Stores/FeedStore.swift` | Add case in `convertToFeedItem` switch (items-based) OR add parsing in `applyFeedResponse` (singleton) |
| 4 | `KaoriApp/Localization/en.json` + `zh-Hans.json` | `"card.xxx": "Xxx"` |

If singleton card: also add field to `FeedAPIDateGroup` struct in `FeedStore.swift`.

### Doc to CREATE

| # | File |
|---|------|
| 1 | `docs/cards/xxx.md` | Use template from `docs/cards/README.md` |
| 2 | Update `docs/cards/README.md` table |

---

## Items-based vs Singleton: Key Differences

### Items-based loader (backend)
```python
async def _load_xxx(date_str: str, group: FeedDateGroup) -> None:
    items = await xxx_service.list_by_date(date_str)
    for item in items:
        group.items.append(FeedItem(
            type=CardType.XXX, id=item["id"], date=date_str,
            created_at=item.get("created_at"), data=item,
        ))
```

### Singleton loader (backend)
```python
async def _load_xxx(date_str: str, group: FeedDateGroup) -> None:
    data = await xxx_service.get_for_date(date_str)
    if data:
        group.xxx = data  # dedicated field on FeedDateGroup
```
Also add the field to `FeedDateGroup` in `models/card.py`.

### iOS `applyFeedResponse` differences

Items-based cards are handled automatically by the existing `convertToFeedItem` switch — just add a case. Singleton cards need explicit parsing in `applyFeedResponse` (see nutrition/summary/portfolio/weather blocks as examples).

### iOS `FeedAPIDateGroup` differences

Singleton cards need a field on `FeedAPIDateGroup`:
```swift
struct FeedAPIDateGroup: Codable {
    // ... existing fields ...
    let xxx: XxxResponse?  // NEW for singleton
}
```

Items-based cards need nothing here — they come through `items: [FeedAPIItem]`.

---

## Editing an Existing Card

### Scope: where changes live

| Change type | Files affected |
|-------------|---------------|
| **Visual only** (feed card appearance) | `Views/Xxx/XxxFeedCard.swift` only |
| **Detail view changes** | `Views/Xxx/XxxDetailView.swift` only |
| **New data field** | Model + repo + API (backend), Model + views (iOS) |
| **New API endpoint** | `api/xxx.py` (backend), APIClient call in view/store (iOS) |
| **Feed behavior** (sort, pinning) | `card_preference_repo.py` defaults (backend), `FeedItem.xxx()` sortPriority (iOS) |
| **Swipe actions** | `XxxCardModule.swift` `feedSwipeActions` or custom swipe methods |
| **Create flow** | `Views/Xxx/XxxCreateView.swift` (iOS), `api/xxx.py` POST endpoint (backend) |
| **Card enable/disable default** | `card_preference_repo.py` `_DEFAULTS` |

### Adding a field to an existing card

**Backend:**
1. Add column to table in `database.py` SCHEMA
2. Add field to Pydantic model in `models/xxx.py`
3. Update repo queries in `storage/xxx_repo.py`
4. Update API endpoint if field is user-settable

**iOS:**
1. Add property to Codable model in `Models/Xxx.swift`
2. Update views that display/edit the field

### Adding an action to a card's swipe menu

In `XxxCardModule.swift`:
- For standard actions: set `feedSwipeActions = [.delete, .regenerate]`
- For custom swipe UI: override `feedTrailingSwipeContent(item:)` or `feedLeadingSwipeContent(item:)`

### Changing how a card appears in the "+" menu

In `XxxCardModule.swift`: set `supportsManualCreation = true/false`. The "+" menu is driven by `CardRegistry.addableModules` — no other file needs editing.

---

## Reference: Key File Locations

### Backend
```
kaori/models/card.py                    # CardType enum, FeedItem, FeedDateGroup
kaori/services/feed_service.py          # CARD_LOADERS registry + loaders
kaori/storage/card_preference_repo.py   # _DEFAULTS dict
kaori/api/router.py                     # include_router lines
kaori/database.py                       # SQL SCHEMA string
```

### iOS
```
KaoriApp/CardModule/CardModule.swift    # Protocol definition (read for all properties)
KaoriApp/CardModule/CardRegistry.swift  # Registry (no manual edits needed)
KaoriApp/CardModule/Modules/            # One file per card type
KaoriApp/Models/FeedItem.swift          # Factory methods + FeedItem struct
KaoriApp/Stores/FeedStore.swift         # applyFeedResponse + convertToFeedItem
KaoriApp/Views/Feed/FeedView.swift      # DO NOT EDIT (registry-driven, no switches)
KaoriApp.swift                          # registry.register() calls
```

### Design docs
```
docs/cards/README.md                    # Index + template
docs/cards/<type>.md                    # Per-card design doc
```

---

## Minimal Example: Post Card (simplest real card)

**Backend files:** `models/post.py` (17 lines), `storage/post_repo.py` (~60 lines), `services/post_service.py` (~30 lines), `api/post.py` (~50 lines)

**iOS files:** `PostCardModule.swift` (34 lines), `PostFeedCard.swift`, `PostDetailView.swift`, `PostCreateView.swift`, `PostListView.swift`

**Registration edits:** 5 backend + 4 iOS files, each ~1 line added.

Use `PostCardModule` as your copy-paste template for new cards.

---

## Design Constraints (enforced)

- Feed cards MUST use `.feedCard()` modifier (iOS)
- Feed cards MUST NOT contain interactive controls (Button, Toggle, TextField, etc.)
- No card-type switches in `FeedView.swift`, `ManageView.swift`, or `ContentView.swift`
- Storage repos own ALL database access (no `get_db()` outside `storage/`)
- Services orchestrate storage + LLM; API routes are thin JSON handlers
