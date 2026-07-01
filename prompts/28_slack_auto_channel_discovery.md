# Prompt 28: Slack Auto Channel Discovery & Sync
Context: The Slack integration currently asks users to manually enter comma-separated channel IDs in the Integrations Hub (`IntegrationConfigDrawer` → `channelIds` field on `SlackConfig`). This is brittle — new channels are invisible until someone copies an ID, and most admins do not know how to find Slack channel IDs. Notion already solves this pattern: when `databaseIds` is left empty, `discover_database_ids()` in `backend/app/services/notion_client.py` auto-discovers every accessible database on each import. Slack should work the same way for channels the bot can read.
Task: Remove the required manual channel-ID workflow and implement automatic discovery and sync of all Slack channels the bot has access to, re-discovering on every sync so newly created or joined channels are picked up without user action.

Requirements:

1. **Backend Slack Client Module (`backend/app/services/slack_client.py`):**
   - Create a dedicated Slack API helper module (mirror the structure of `notion_client.py`).
   - Implement `list_accessible_channels(token: str) -> list[dict]` that paginates `conversations.list` (`https://slack.com/api/conversations.list`) with:
     - `types=public_channel,private_channel`
     - `exclude_archived=true`
     - Cursor-based pagination until `has_more` is false.
   - Return normalized channel objects containing at minimum: `id`, `name`, `is_private`, `is_member`, `num_members` (when present).
   - Implement `discover_channel_ids(token: str) -> list[str]` that returns IDs for channels where `is_member` is true (channels the bot has actually joined). Skip channels the bot cannot read.
   - Implement `fetch_channel_history(token: str, channel_id: str, *, limit: int = 200)` wrapping `conversations.history` for message ingestion during sync.
   - Handle Slack API errors (`ok: false`) with descriptive `ValueError` messages, consistent with `validate_slack_bot_token` and the Notion client.

2. **Auto-Discovery on Sync (Notion Parity):**
   - When syncing Slack content, **always re-run channel discovery** — do not treat a stored channel list as the source of truth.
   - If `channelIds` is empty or absent, discover and sync **all** member channels automatically.
   - If `channelIds` is provided (optional override), restrict sync to that explicit allowlist — same opt-in narrowing pattern as Notion's optional `databaseIds`.
   - Newly created channels that the bot is invited to must appear on the next sync without any configuration change.

3. **Extend Token Validation (`backend/app/services/integration_validate.py`):**
   - After `auth.test` succeeds, call `discover_channel_ids` and enrich the validation response message (like Notion reports database/page counts):
     - Example: `Slack token valid — bot on Acme. Found 14 accessible channel(s).`
   - If discovery fails due to missing OAuth scopes, return a clear error naming the required scopes (see item 5).

4. **Slack Sync Pipeline (`backend/app/services/integration_sync.py` + routes):**
   - Add Slack to the backend sync path currently used by GitHub and Jira (`process_external_app_sync` or a parallel `process_slack_sync`).
   - On sync:
     1. Resolve channel IDs via auto-discovery (or optional allowlist).
     2. For each channel, pull recent message history and build a narrative payload (channel name, participants, thread snippets, incident keywords).
     3. Ingest into Cognee via `tenant_add_and_cognify` with a Slack-specific extraction prompt (incident threads, on-call announcements, engineering channel metadata).
   - Expose via existing integration routes (`POST /api/integrations/{source}/sync` or equivalent) so the frontend can trigger it.
   - Return sync telemetry: `channels_discovered`, `channels_synced`, `messages_ingested`.

5. **OAuth Scopes & Setup Guide Updates:**
   - Update `frontend/src/lib/integration-setup-guides.ts` Slack steps:
     - Add Bot Token Scopes: `channels:history`, `groups:history`, `channels:read`, `groups:read` (in addition to existing `users:read`, `users:read.email`).
     - **Remove** the step instructing users to copy channel IDs manually.
     - State clearly: *"Empulse auto-discovers all channels the bot is a member of — invite the bot to any channel you want synced."*
   - Document that private channels require explicitly `/invite`ing the bot; public channels may also require invitation depending on workspace settings.

6. **Frontend Config UI (`IntegrationConfigDrawer.tsx`, `integrations.ts`, `IntegrationsContext.tsx`):**
   - **Remove** the required "Channel IDs" text input from the default Slack setup flow.
   - Replace with an informational callout (similar tone to Notion's auto-discovery hint):
     - *"All channels the bot has joined will be synced automatically. Re-sync anytime to pick up new channels."*
   - Optionally retain a collapsed "Advanced: limit to channel IDs" field for power users who want an allowlist — placeholder: `Leave empty for auto-discovery`.
   - Remove `channelIds` from `credentialFields` in `IntegrationsContext` if it is no longer a credential (optional override should not invalidate `validated` on change).
   - Add `"slack"` to `BACKEND_SYNC_SOURCES` so Connect/Sync triggers the real backend pipeline instead of the current local mock delay.

7. **Migration & Backward Compatibility:**
   - Existing users with `channelIds` stored in localStorage should continue to work: non-empty value = allowlist mode; empty value = full auto-discovery.
   - Do not break `fetch-users` / employee master import (`employee_master_fetch.py` → `_fetch_slack_users_live`) — channel discovery is orthogonal to `users.list`.

8. **Testing:**
   - Add unit tests for `discover_channel_ids` with mocked `conversations.list` pagination responses (multi-page cursor, archived exclusion, non-member channel filtering).
   - Add a test that sync with empty `channelIds` discovers and processes all member channels.
   - Add a test that an explicit allowlist overrides auto-discovery.
