# Integration Sync

**Route:** Settings → Integrations (sync actions)  
**Audience:** Platform admins, tenant admins

Orchestrates **GitHub, Jira, Notion, and Slack** ingestion into Cognee and operational Postgres. Refreshes telemetry that feeds ERA, KRA, and component auto-provisioning.

## Capabilities

- Per-source and global sync (`POST /api/integrations/sync`)
- Background jobs with progress (`integration_sync_jobs`)
- GitHub: tree walk, blame, PRs, reviews, component provisioning
- Jira: issues, components, assignees
- Notion: doc inventory (API or `notion-docs/` repo pack)
- Slack: threads and escalations
- Post-sync: ERA snapshot refresh, org-chart finalize, GitHub ownership → assignments

## Mapped source paths

- `backend/app/services/integration_sync.py`
- `backend/app/services/integration_sync_jobs.py`
- `backend/app/services/integration_telemetry.py`
- `backend/app/services/integration_config_store.py`
- `backend/app/services/integration_validate.py`
- `backend/app/services/github_repo_sync.py`
- `backend/app/services/github_client.py`
- `backend/app/services/github_code.py`
- `backend/app/services/github_evidence.py`
- `backend/app/services/jira_client.py`
- `backend/app/services/jira_mapper.py`
- `backend/app/services/notion_client.py`
- `backend/app/services/notion_repo_pack.py`
- `backend/app/services/slack_client.py`
- `backend/app/services/component_provisioning.py`
- `backend/app/services/component_management.py`
- `backend/app/routes/integrations.py`
- `backend/tests/test_integration_sync_jobs.py`
- `backend/tests/test_github_repo_sync.py`
- `backend/tests/test_component_provisioning.py`
- `frontend/src/components/integrations/`
- `notion-docs/runbooks/02-integration-sync.md`
- `notion-docs/design/06-integrations-platform.md`

## Sync → attribution pipeline

```
integration_sync
  → github_repo_sync (blame, PRs)
  → path_component_map (from component_provisioning + docs/features paths)
  → identity_resolver (provider_user_id → employee_id)
  → integration_telemetry → era_analytics / kra
```

### Recommended order for new tenants

1. Connect integrations (Settings)
2. Import org chart / employees
3. **Sync** all providers
4. Complete **Identity Mapping** and Save
5. **Sync** again (reconcile quarantine, refresh scores)
6. Review ERA command center

## Related

- [Identity Mapping](../identity-mapping/README.md)
- [ERA](../era/README.md)
- Feature component map: [docs/features/README.md](../README.md)
