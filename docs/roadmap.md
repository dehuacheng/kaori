# Kaori — Roadmap

## Phase 1: MVP — Diet + Weight + Profile (Current)

See individual feature docs: [meals.md](meals.md), [weight.md](weight.md), [profile.md](profile.md)

## Phase 2: Tailscale + iPhone Access
- Tailscale on MacBook + iPhone
- HTTPS, PWA install from Safari
- Test full mobile flow

## Phase 3: Proactive Notifications (requires iOS frontend)
- Daily meal reminders
- Weight tracking reminders
- Anomaly alerts (missed meals, weight spikes)

## Phase 4: AI Coaching
- Chat interface with roles (trainer, nutritionist, doctor, therapist)
- Context builder + de-identification pipeline
- Daily AI health brief

## Phase 5: Additional Data Domains
- Exercise tracking (structured logging) ✅
- Symptom logging (migraine-specific)
- Diary / mood / energy tracking
- Calendar integration
- Todo list

## Phase 6: Feed-Based UI Revamp
- Unified "news feed" timeline for all daily entries (meals, weight, workouts, diary)
- Redesigned "add item" flow — feels like posting to the feed
- **Scenes** — curated toolkits for specific activities (gym workout, deep focus study, etc.)
- Each scene provides contextual mini-tools and quick actions

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
