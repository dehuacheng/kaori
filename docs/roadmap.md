# Kaori — Roadmap

## Phase 1: MVP — Diet + Weight + Profile (Current)

See individual feature docs: [meals.md](meals.md), [weight.md](weight.md), [profile.md](profile.md)

## Phase 2: Tailscale + iPhone Access
- Tailscale on MacBook + iPhone
- HTTPS, PWA install from Safari
- Test full mobile flow

## Phase 3: Proactive Notifications ✅
- Daily meal reminders (breakfast, lunch, dinner at configurable times) ✅
- Weight tracking reminders (morning check-in) ✅
- LLM-generated daily and weekly health summaries ✅
- Inline dashboard display with collapsible sections ✅
- Anomaly alerts (missed meals, weight spikes) — deferred

## Phase 4: AI Coaching
- Chat interface with roles (trainer, nutritionist, doctor, therapist)
- Context builder + de-identification pipeline
- Daily AI health brief ✅ (via daily/weekly summary)

## Phase 5: Additional Data Domains
- Exercise tracking (structured logging) ✅
- Symptom logging (migraine-specific)
- Diary / mood / energy tracking
- Calendar integration
- Todo list

## Phase 6: Feed-Based UI Revamp ✅
- Unified "news feed" timeline for all daily entries (meals, weight, workouts) ✅
- Multi-day infinite scroll with day headers ✅
- Rich feed cards (Apple Health–inspired dark aesthetic) ✅
- Daily nutrition progress bars (calories, protein, carbs, fat) ✅
- AI daily/weekly summary cards with swipe-to-regenerate ✅
- iOS 18 Control Center–style "+" add menu (meal, weight, workout) ✅
- Analytics view (calorie chart, weight chart) as sheet from feed ✅
- 3-tab layout: Home (feed) | + (add) | More (data, tools, profile, settings) ✅
- Swipe-to-delete on all feed items, tap to navigate to detail views ✅
- **Scenes** — curated toolkits for specific activities — deferred

## Phase 7: Personal Document Vault
- Upload and retrieve personal documents (passport, IDs, etc.)
- Password/Face ID protection
- Dual-mode design: full LLM assistant mode (rich querying) vs. static presentation mode (maximum security)
- User chooses mode based on their LLM setup and risk tolerance

## Phase 8: Medical Record Keeper
- Store exam results, lab work, and health records
- AI-powered PCP, nutritionist, and personal trainer — all in one
- HealthKit XML export parser
- Lab result trending, medication adherence

## Phase 9: Personal AI Assistant (Long-Term Vision)
- Full personal AI assistant (Kaori by default — user can customize the name)
- Comprehensive care across all aspects of life
- Core principle: **your data stays in your hands** — self-host or choose a trusted LLM provider
- Local LLM support (e.g., Qwen2.5-VL via MLX for free on-device analysis)
- App is completely free and open-source — fork and vibe-code it to make it yours
