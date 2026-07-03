"""Tests for Cognee Cloud connection and structured ingest serialization."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from cognee.infrastructure.engine import DataPoint

from app.services.cognee_cloud import (
    bootstrap_cognee_startup_migrations,
    configure_cognee_backend,
    connect_cognee_cloud,
    ensure_cloud_tenant_dataset,
    is_cognee_cloud_mode,
    push_tenant_ontology_graph,
    serialize_datapoints_for_cloud,
)
from app.services.tenant_cognee import tenant_add_data_points


class SampleNode(DataPoint):
    external_id: str
    name: str
    metadata: dict = {"index_fields": ["name"]}


def test_serialize_datapoints_for_cloud_includes_type_and_fields():
    payload = serialize_datapoints_for_cloud(
        [SampleNode(external_id="c1", name="Payments API")]
    )
    assert "SampleNode" in payload
    assert "Payments API" in payload
    assert "external_id" in payload


def test_is_cognee_cloud_mode_false_when_backend_local():
    with patch("app.config.get_settings") as settings_mock, patch(
        "cognee.api.v1.serve.state.get_remote_client",
        return_value=MagicMock(),
    ):
        settings_mock.return_value.cognee_backend = "local"
        assert is_cognee_cloud_mode() is False


def test_is_cognee_cloud_mode_false_without_client():
    with patch("app.config.get_settings") as settings_mock, patch(
        "cognee.api.v1.serve.state.get_remote_client",
        return_value=None,
    ):
        settings_mock.return_value.cognee_backend = "cloud"
        assert is_cognee_cloud_mode() is False


def test_is_cognee_cloud_mode_true_when_cloud_and_connected():
    with patch("app.config.get_settings") as settings_mock, patch(
        "cognee.api.v1.serve.state.get_remote_client",
        return_value=MagicMock(),
    ):
        settings_mock.return_value.cognee_backend = "cloud"
        assert is_cognee_cloud_mode() is True


def test_configure_cognee_backend_local_disconnects():
    with patch("app.config.get_settings") as settings_mock, patch(
        "cognee.disconnect",
        new_callable=AsyncMock,
    ) as disconnect_mock:
        settings_mock.return_value.cognee_backend = "local"
        assert asyncio.run(configure_cognee_backend()) == "local"
        disconnect_mock.assert_awaited_once()


def test_configure_cognee_backend_cloud_requires_url():
    with patch("app.config.get_settings") as settings_mock:
        settings_mock.return_value.cognee_backend = "cloud"
        settings_mock.return_value.cognee_service_url = ""
        settings_mock.return_value.cognee_api_key = ""
        try:
            asyncio.run(configure_cognee_backend())
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "COGNEE_SERVICE_URL" in str(exc)


def test_configure_cognee_backend_cloud_calls_serve():
    with patch("app.config.get_settings") as settings_mock, patch(
        "cognee.serve",
        new_callable=AsyncMock,
    ) as serve_mock:
        settings_mock.return_value.cognee_backend = "cloud"
        settings_mock.return_value.cognee_service_url = "https://tenant.aws.cognee.ai"
        settings_mock.return_value.cognee_api_key = "ck_test"
        assert asyncio.run(configure_cognee_backend()) == "cloud"
        serve_mock.assert_awaited_once_with(
            url="https://tenant.aws.cognee.ai",
            api_key="ck_test",
        )


def test_connect_cognee_cloud_false_for_local_backend():
    with patch(
        "app.services.cognee_cloud.configure_cognee_backend",
        new_callable=AsyncMock,
        return_value="local",
    ):
        assert asyncio.run(connect_cognee_cloud()) is False


def test_serialize_datapoints_for_cloud_includes_ontology_edges():
    from cognee.infrastructure.engine.models.Edge import Edge

    class LinkedNode(DataPoint):
        external_id: str
        name: str
        owns: Any = None
        metadata: dict = {"index_fields": ["name"]}

    target = SampleNode(external_id="c2", name="Billing")
    node = LinkedNode(
        external_id="e1",
        name="Ada",
        owns=(Edge(relationship_type="ownsComponent"), target),
    )
    payload = serialize_datapoints_for_cloud([node])
    assert "ownsComponent" in payload
    assert "target_external_id" in payload
    assert "c2" in payload


def test_ensure_cloud_tenant_dataset_calls_remember():
    with patch(
        "app.services.cognee_cloud.is_cognee_cloud_mode",
        return_value=True,
    ), patch(
        "cognee.remember",
        new_callable=AsyncMock,
    ) as remember_mock:
        asyncio.run(ensure_cloud_tenant_dataset("empulse_tenant_abc"))

    remember_mock.assert_awaited_once()
    assert remember_mock.await_args.kwargs["dataset_name"] == "empulse_tenant_abc"


def test_push_tenant_ontology_graph_uses_preserve_mode():
    push_result = MagicMock(
        status="success",
        num_nodes=12,
        num_edges=8,
        pipeline_run_id="run-1",
    )
    with patch(
        "app.services.cognee_cloud.is_cognee_cloud_mode",
        return_value=True,
    ), patch(
        "cognee.push",
        new_callable=AsyncMock,
        return_value=push_result,
    ) as push_mock:
        result = asyncio.run(push_tenant_ontology_graph("empulse_tenant_abc"))

    push_mock.assert_awaited_once_with(
        "empulse_tenant_abc",
        target_dataset="empulse_tenant_abc",
        mode="preserve",
        run_in_background=False,
    )
    assert result["num_nodes"] == 12
    assert result["num_edges"] == 8


def test_push_tenant_ontology_graph_skips_empty_export():
    with patch(
        "app.services.cognee_cloud.is_cognee_cloud_mode",
        return_value=True,
    ), patch(
        "cognee.push",
        new_callable=AsyncMock,
        side_effect=ValueError("Dataset 'x' exported 0 nodes — nothing to push."),
    ):
        result = asyncio.run(push_tenant_ontology_graph("empulse_tenant_abc"))

    assert result is None


def test_skip_local_vector_indexing_for_cloud_patches_indexers():
    from app.services import cognee_cloud
    from app.services.cognee_cloud import skip_local_vector_indexing_for_cloud

    async def _run():
        import importlib

        add_module = importlib.import_module("cognee.tasks.storage.add_data_points")

        async with skip_local_vector_indexing_for_cloud():
            assert add_module.index_data_points is cognee_cloud._noop_index_data_points
            assert add_module.index_graph_edges is cognee_cloud._noop_index_graph_edges

    with patch(
        "app.services.cognee_cloud.use_cognee_cloud_backend",
        return_value=True,
    ):
        asyncio.run(_run())


def test_tenant_add_data_points_pushes_ontology_after_local_ingest():
    tenant_id = __import__("uuid").uuid4()
    node = SampleNode(external_id="e1", name="Ada")

    with patch(
        "app.services.cognee_cloud.is_cognee_cloud_mode",
        return_value=True,
    ), patch(
        "app.services.tenant_cognee.tenant_cognee_context",
    ) as ctx_mock, patch(
        "app.services.tenant_cognee.add_data_points",
        new_callable=AsyncMock,
    ) as add_points_mock, patch(
        "app.services.cognee_cloud.push_tenant_ontology_graph",
        new_callable=AsyncMock,
        return_value={"num_nodes": 1, "num_edges": 0},
    ) as push_mock, patch(
        "app.services.tenant_cognee.resolve_authorized_user_dataset",
        new_callable=AsyncMock,
        return_value=(MagicMock(), MagicMock()),
    ), patch(
        "app.services.tenant_cognee.ensure_structured_ingest_data_item",
        new_callable=AsyncMock,
        return_value=MagicMock(),
    ), patch(
        "app.services.tenant_cognee.get_default_user",
        new_callable=AsyncMock,
        return_value=MagicMock(),
    ), patch(
        "app.services.tenant_cognee.tag_datapoints_with_dataset",
        side_effect=lambda points, _name: points,
    ), patch(
        "app.services.cognee_cloud.skip_local_vector_indexing_for_cloud",
    ) as skip_ctx_mock:
        skip_ctx_mock.return_value.__aenter__ = AsyncMock(return_value=None)
        skip_ctx_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        ctx_mock.return_value.__aenter__ = AsyncMock(return_value="empulse_tenant_test")
        ctx_mock.return_value.__aexit__ = AsyncMock(return_value=False)

        asyncio.run(tenant_add_data_points(tenant_id, [node]))

    add_points_mock.assert_awaited_once()
    push_mock.assert_awaited_once_with("empulse_tenant_test")


def test_tenant_add_and_cognify_uses_remember_on_cloud_backend():
    from app.services.tenant_cognee import tenant_add_and_cognify

    tenant_id = __import__("uuid").uuid4()

    with patch(
        "app.services.cognee_cloud.use_cognee_cloud_backend",
        return_value=True,
    ), patch(
        "app.ontology.enrichment.cognify_enrichment_available",
        return_value=True,
    ), patch(
        "app.services.tenant_cognee.tenant_cognee_context",
    ) as ctx_mock, patch(
        "cognee.remember",
        new_callable=AsyncMock,
        return_value={"status": "ok"},
    ) as remember_mock:
        ctx_mock.return_value.__aenter__ = AsyncMock(return_value="empulse_tenant_test")
        ctx_mock.return_value.__aexit__ = AsyncMock(return_value=False)

        result = asyncio.run(
            tenant_add_and_cognify("narrative", tenant_id, custom_prompt="prompt"),
        )

    remember_mock.assert_awaited_once()
    args, kwargs = remember_mock.await_args
    assert args[0] == "narrative"
    assert kwargs["custom_prompt"] == "prompt"
    assert kwargs["dataset_name"].startswith("empulse_tenant_")
    assert result["skipped"] is False


def test_bootstrap_startup_migrations_cloud_skips_full_graph_chain():
    create_db = AsyncMock()
    stamp = AsyncMock()
    relational = AsyncMock()
    schema_exists = AsyncMock(return_value=False)

    with patch(
        "app.services.cognee_cloud.use_cognee_cloud_backend",
        return_value=True,
    ), patch(
        "cognee.modules.migrations.startup._relational_schema_exists",
        schema_exists,
    ), patch(
        "cognee.infrastructure.databases.relational.get_relational_engine",
    ) as engine_mock, patch(
        "cognee.modules.migrations.startup.run_relational_migrations",
        relational,
    ), patch(
        "cognee.modules.migrations.startup.run_relational_stamp",
        stamp,
    ), patch("cognee.run_migrations.run_migrations") as full_migrations:
        engine_mock.return_value.create_database = create_db
        failed = asyncio.run(bootstrap_cognee_startup_migrations())

    assert failed == []
    create_db.assert_awaited_once()
    stamp.assert_awaited_once_with("head")
    relational.assert_not_awaited()
    full_migrations.assert_not_called()


def test_bootstrap_startup_migrations_local_runs_full_chain():
    with patch(
        "app.services.cognee_cloud.use_cognee_cloud_backend",
        return_value=False,
    ), patch(
        "cognee.run_migrations.run_migrations",
        new_callable=AsyncMock,
        return_value=[],
    ) as full_migrations:
        failed = asyncio.run(bootstrap_cognee_startup_migrations())

    assert failed == []
    full_migrations.assert_awaited_once()
