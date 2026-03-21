# AI Coding Guidelines

## Context & Documentation (Context7 MCP)

Always use Context7 MCP for library/API documentation, code generation, setup, and configuration questions without requiring the user to explicitly ask.
If the user provides an explicit Context7 library ID (for example, `/supabase/supabase`), skip library resolution and query that library directly.
If the user specifies a library version, prefer that version's documentation.
If Context7 is unavailable, state that briefly and fall back to official documentation.
