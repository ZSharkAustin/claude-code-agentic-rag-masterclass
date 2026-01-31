# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability
- [x] 1.1 Frontend scaffolding (Vite + React + TS + Tailwind + shadcn)
- [x] 1.2 Backend scaffolding (FastAPI + venv + dependencies)
- [x] 1.3 Environment config files (.env.example, .gitignore)
- [x] 2.1 Database schema with RLS (threads table + policies)
- [x] 2.2 Frontend auth (Supabase client, AuthContext, AuthPage, UserMenu)
- [x] 2.3 Backend auth middleware (get_current_user, get_supabase_client)
- [x] 3.1 Chat layout with thread sidebar
- [x] 3.2 Message display and input components
- [x] 4.1 Thread CRUD API endpoints
- [x] 4.2 Chat SSE endpoint with OpenAI Responses API
- [x] 4.3 Frontend SSE consumption (fetch + ReadableStream)
- [x] 4.4 Auto-generate thread titles
- [x] 5.1 LangSmith tracing (wrap_openai + @traceable)
- [x] 6.1 End-to-end smoke test
- [x] 6.2 Error handling verification

### Module 2: BYO Retrieval + Memory
- [x] 1.1 Database schema (messages, documents, chunks, pgvector, match_chunks, storage bucket)
- [x] 1.2 Switch to Chat Completions API (OpenRouter) + message history
- [x] 1.3 Messages router (GET /api/threads/{id}/messages)
- [x] 2.1 pypdf dependency
- [x] 2.2 Document Pydantic models
- [x] 2.3 Document processing service (extract, chunk, embed, store)
- [x] 2.4 Documents router (POST/GET/DELETE /api/documents)
- [x] 2.5 RAG tool calling (search_documents tool in chat endpoint)
- [x] 3.1 Load message history on thread select
- [x] 3.2 API upload helper (multipart FormData)
- [x] 3.3 useDocuments hook with Supabase Realtime
- [x] 3.4 Documents page (upload, list, status badges, delete)
- [x] 3.5 Tab navigation (Chat / Documents)

### Module 3: Record Manager
- [x] 1.1 Database migration (content_hash column + unique index + lookup index)
- [x] 1.2 Update DocumentResponse model (content_hash field)
- [x] 1.3 Content hash computation + dedup check at upload time (SHA-256, 409 on duplicate)
