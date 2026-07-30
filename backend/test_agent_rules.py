import json
import os
import shutil
import tempfile
import unittest
import uuid

from pydantic import ValidationError


TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-agent-rules-test-")
os.environ.setdefault("DATA_DIR", TEST_DATA_DIR)

from backend import main  # noqa: E402
from backend.agent_rules import (  # noqa: E402
    AgentRuleError,
    AgentRuleService,
    CompiledRule,
    SPECIFICATION_VERSION,
)


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


def compiled_rule():
    return {
        "schema_version": "1.2",
        "kind": "execution",
        "title": "收费站查询规则",
        "summary": "按用户给定的条件查询收费站流水。",
        "execution_rules": [
            {
                "id": "station_query",
                "priority": 80,
                "when": {
                    "all": ["用户请求收费站流水"],
                    "any": [],
                    "none": [],
                },
                "instructions": ["按用户给定的条件调用查询工具。"],
                "tools": [
                    {
                        "selector": "收费站流水查询工具",
                        "names": [],
                        "argument_defaults": {},
                        "argument_constants": {},
                    }
                ],
                "response_requirements": [],
            }
        ],
        "clarification_rules": [],
    }


def record_presentation_rule():
    return {
        "schema_version": "1.2",
        "kind": "record_presentation",
        "title": "业务记录展示规则",
        "summary": "默认总结，明确索要记录时展示原始记录。",
        "execution_rules": [],
        "record_presentation": {
            "applies_to": "structured_business_records",
            "default_mode": "summary",
        },
        "clarification_rules": [],
    }


def deterministic_pagination_rule(
    tool_name="query_entry_transaction",
):
    return {
        "schema_version": "1.2",
        "kind": "deterministic_pagination",
        "title": "入口流水完整分页规则",
        "summary": "保持查询区间不变，逐页查询直到空页。",
        "execution_rules": [],
        "deterministic_pagination": {
            "tool_name": tool_name,
            "cursor_argument": "page_number",
            "start": 1,
            "step": 1,
            "page_size_argument": "page_size",
            "page_size": 100,
            "stop_when": "empty_result",
            "max_pages": 96,
        },
        "clarification_rules": [],
    }


class AgentRuleServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user_id = str(uuid.uuid4())
        self.admin_id = str(uuid.uuid4())
        self.other_admin_id = str(uuid.uuid4())
        now = "2026-07-26T00:00:00Z"
        with main.db.connection(write=True) as connection:
            connection.executemany(
                """
                INSERT INTO users (
                    id, username, password_hash, role, enabled,
                    created_at, updated_at, password_changed_at
                ) VALUES (?, ?, 'hash', 'member', 1, ?, ?, ?)
                """,
                [
                    (
                        self.user_id,
                        f"agent-rule-{self.user_id}",
                        now,
                        now,
                        now,
                    ),
                ],
            )
            for user_id, role in (
                (self.admin_id, "admin"),
                (self.other_admin_id, "admin"),
            ):
                connection.execute(
                    """
                    INSERT INTO users (
                        id, username, password_hash, role, enabled,
                        created_at, updated_at, password_changed_at
                    ) VALUES (?, ?, 'hash', ?, 1, ?, ?, ?)
                    """,
                    (
                        user_id,
                        f"agent-rule-{user_id}",
                        role,
                        now,
                        now,
                        now,
                    ),
                )
        self.model_outputs = []
        self.audits = []

        async def compile_model(request):
            self.model_outputs.append(request)
            return {"content": json.dumps(compiled_rule())}

        self.service = AgentRuleService(
            main.db.connection,
            compile_model=compile_model,
            audit=lambda *args: self.audits.append(args),
            audit_in_transaction=(
                lambda _connection, *args: self.audits.append(args)
            ),
        )

    async def asyncTearDown(self):
        with main.db.connection(write=True) as connection:
            document_ids = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT id FROM agent_rule_documents
                    WHERE owner_user_id IN (?, ?, ?)
                    """,
                    (
                        self.user_id,
                        self.admin_id,
                        self.other_admin_id,
                    ),
                ).fetchall()
            ]
            for document_id in document_ids:
                connection.execute(
                    """
                    DELETE FROM module_task_rule_activations
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )
                connection.execute(
                    """
                    DELETE FROM agent_compiled_rule_versions
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )
                connection.execute(
                    """
                    DELETE FROM agent_rule_source_versions
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )
            connection.execute(
                """
                DELETE FROM agent_rule_documents
                WHERE owner_user_id IN (?, ?, ?)
                """,
                (
                    self.user_id,
                    self.admin_id,
                    self.other_admin_id,
                ),
            )
            connection.execute(
                """
                DELETE FROM audit_log
                WHERE actor_user_id IN (?, ?, ?)
                """,
                (
                    self.user_id,
                    self.admin_id,
                    self.other_admin_id,
                ),
            )
            connection.execute(
                "DELETE FROM users WHERE id IN (?, ?, ?)",
                (
                    self.user_id,
                    self.admin_id,
                    self.other_admin_id,
                ),
            )

    async def test_source_compile_validate_activate_and_version(self):
        created = self.service.create_document(
            self.user_id,
            name="收费站规则",
            source_document=(
                "分页查询，每页 20 条；page 从 1 开始递增，"
                "直到返回空数据。"
            ),
        )
        document_id = created["id"]
        source_id = created["current_source_version_id"]

        compiled = await self.service.compile_document(
            self.user_id,
            document_id,
            source_version_id=source_id,
        )
        candidate = compiled["compiled_candidates"][0]
        self.assertEqual(candidate["status"], "valid")
        self.assertEqual(
            candidate["specification_version"],
            SPECIFICATION_VERSION,
        )
        self.assertEqual(candidate["validation_errors"], [])
        self.assertEqual(
            candidate["compiled_rule"]["schema_version"],
            "1.2",
        )
        self.assertEqual(
            self.model_outputs[0]["profile"],
            "agent-compiler",
        )

        active = self.service.activate(
            self.user_id,
            document_id,
            compiled_version_id=candidate["id"],
        )
        self.assertEqual(
            active["active_compiled_version_id"],
            candidate["id"],
        )
        self.assertEqual(
            self.service.active_snapshots(self.user_id)[0][
                "compiled_version_id"
            ],
            candidate["id"],
        )

        updated = self.service.update_source(
            self.user_id,
            document_id,
            expected_source_version_id=source_id,
            source_document="更新：每页 50 条，直到空页。",
        )
        self.assertNotEqual(
            updated["current_source_version_id"],
            source_id,
        )
        self.assertEqual(
            updated["active_compiled_version_id"],
            candidate["id"],
        )
        with self.assertRaises(AgentRuleError) as conflict:
            self.service.update_source(
                self.user_id,
                document_id,
                expected_source_version_id=source_id,
                source_document="过期编辑",
            )
        self.assertEqual(conflict.exception.status_code, 409)

    async def test_invalid_candidate_is_retained_but_cannot_activate(self):
        async def invalid_model(_request):
            return {"content": '{"schema_version":"1.0"}'}

        service = AgentRuleService(
            main.db.connection,
            compile_model=invalid_model,
            audit=lambda *_args: None,
            audit_in_transaction=lambda _connection, *_args: None,
        )
        created = service.create_document(
            self.user_id,
            name="无效候选",
            source_document="查询数据。",
        )
        compiled = await service.compile_document(
            self.user_id,
            created["id"],
            source_version_id=created["current_source_version_id"],
        )
        candidate = compiled["compiled_candidates"][0]
        self.assertEqual(candidate["status"], "invalid")
        self.assertTrue(candidate["validation_errors"])
        with self.assertRaises(AgentRuleError) as invalid:
            service.activate(
                self.user_id,
                created["id"],
                compiled_version_id=candidate["id"],
            )
        self.assertEqual(invalid.exception.status_code, 409)

    async def test_legacy_rule_contracts_remain_readable_with_v10_iteration(
        self,
    ):
        legacy_v10 = compiled_rule()
        legacy_v10["schema_version"] = "1.0"
        legacy_v10.pop("kind")
        legacy_v10["execution_rules"][0]["tools"][0]["iteration"] = {
            "cursor_argument": "page",
            "start": 1,
            "step": 1,
            "page_size_argument": "page_size",
            "page_size": 100,
            "stop_when": "empty_result",
            "stop_description": "",
            "max_calls": 96,
        }
        parsed_v10 = CompiledRule.model_validate(legacy_v10)
        self.assertEqual(parsed_v10.schema_version, "1.0")
        self.assertEqual(
            parsed_v10.execution_rules[0].tools[0].iteration.cursor_argument,
            "page",
        )
        self.assertTrue(parsed_v10.uses_bulk_iteration())

        legacy_execution = compiled_rule()
        legacy_execution["schema_version"] = "1.1"
        self.assertEqual(
            CompiledRule.model_validate(legacy_execution).schema_version,
            "1.1",
        )

        legacy_presentation = record_presentation_rule()
        legacy_presentation["schema_version"] = "1.1"
        self.assertEqual(
            CompiledRule.model_validate(legacy_presentation).kind,
            "record_presentation",
        )

        bad_iteration = compiled_rule()
        bad_iteration["schema_version"] = "1.1"
        bad_iteration["execution_rules"][0]["tools"][0]["iteration"] = {
            "cursor_argument": "page",
            "start": 1,
            "step": 1,
            "stop_when": "empty_result",
            "max_calls": 10,
        }
        with self.assertRaises(Exception):
            CompiledRule.model_validate(bad_iteration)

    async def test_deterministic_pagination_accepts_1024_page_hard_limit(
        self,
    ):
        rule = deterministic_pagination_rule()
        rule["deterministic_pagination"]["max_pages"] = 1024
        parsed = CompiledRule.model_validate(rule)
        self.assertEqual(
            parsed.deterministic_pagination.max_pages,
            1024,
        )
        self.assertTrue(parsed.uses_bulk_iteration())

        rule["deterministic_pagination"]["max_pages"] = 1025
        with self.assertRaises(ValidationError):
            CompiledRule.model_validate(rule)

    async def test_scope_defaults_personal_and_member_cannot_create_system(self):
        personal = self.service.create_document(
            self.user_id,
            name="旧客户端默认个人",
            source_document="保持个人规则。",
        )
        self.assertEqual(personal["scope"], "personal")
        self.assertTrue(personal["editable"])

        with self.assertRaises(AgentRuleError) as denied:
            self.service.create_document(
                self.user_id,
                name="越权系统规则",
                source_document="不应创建。",
                scope="system_default",
            )
        self.assertEqual(denied.exception.code, "administrator_required")
        self.assertEqual(denied.exception.status_code, 403)

    async def test_system_metadata_is_visible_but_detail_is_admin_only(self):
        system = self.service.create_document(
            self.admin_id,
            name="系统默认",
            source_document="默认总结业务记录。",
            scope="system_default",
            is_admin=True,
        )

        member_rows = self.service.list_documents(self.user_id)
        listed = next(
            row for row in member_rows
            if row["name"] == system["name"]
        )
        self.assertEqual(
            set(listed),
            {
                "name",
                "scope",
                "editable",
                "active",
                "active_compiled_version_id",
                "active_specification_version",
                "active_content_sha256",
            },
        )
        self.assertEqual(listed["scope"], "system_default")
        self.assertFalse(listed["editable"])
        self.assertFalse(listed["active"])

        with self.assertRaises(AgentRuleError) as denied:
            self.service.get_document(self.user_id, system["id"])
        self.assertEqual(denied.exception.status_code, 403)

        managed = self.service.get_document(
            self.other_admin_id,
            system["id"],
            is_admin=True,
        )
        self.assertEqual(managed["id"], system["id"])
        updated = self.service.update_source(
            self.other_admin_id,
            system["id"],
            expected_source_version_id=system[
                "current_source_version_id"
            ],
            source_document="由另一位当前管理员更新。",
            is_admin=True,
        )
        self.assertNotEqual(
            updated["current_source_version_id"],
            system["current_source_version_id"],
        )
        compiled = await self.service.compile_document(
            self.other_admin_id,
            system["id"],
            source_version_id=updated["current_source_version_id"],
            is_admin=True,
        )
        candidate = compiled["compiled_candidates"][0]
        self.service.activate(
            self.other_admin_id,
            system["id"],
            compiled_version_id=candidate["id"],
            is_admin=True,
        )
        listed_active = next(
            row
            for row in self.service.list_documents(self.user_id)
            if row["name"] == system["name"]
        )
        self.assertTrue(listed_active["active"])
        self.assertEqual(
            listed_active["active_compiled_version_id"],
            candidate["id"],
        )
        self.assertEqual(
            listed_active["active_specification_version"],
            "chatraw-agent-rule-1.2",
        )
        self.assertEqual(
            listed_active["active_content_sha256"],
            candidate["content_sha256"],
        )
        self.assertNotIn("id", listed_active)
        self.assertNotIn("current_source_version_id", listed_active)
        self.assertNotIn("active_source_version_id", listed_active)

    async def test_system_activation_rejects_stale_source_candidate(self):
        system = self.service.create_document(
            self.admin_id,
            name="系统候选必须最新",
            source_document="默认总结。",
            scope="system_default",
            is_admin=True,
        )
        compiled = await self.service.compile_document(
            self.admin_id,
            system["id"],
            source_version_id=system["current_source_version_id"],
            is_admin=True,
        )
        candidate = compiled["compiled_candidates"][0]
        self.assertEqual(candidate["status"], "valid")
        self.service.update_source(
            self.admin_id,
            system["id"],
            expected_source_version_id=system[
                "current_source_version_id"
            ],
            source_document="默认总结，并保留文件生成。",
            is_admin=True,
        )

        with self.assertRaises(AgentRuleError) as stale:
            self.service.activate(
                self.admin_id,
                system["id"],
                compiled_version_id=candidate["id"],
                is_admin=True,
            )
        self.assertEqual(stale.exception.code, "system_rule_candidate_stale")

    async def test_soft_delete_hides_rule_preserves_versions_and_allows_name_reuse(
        self,
    ):
        created = self.service.create_document(
            self.user_id,
            name="可删除规则",
            source_document="按条件查询。",
        )
        compiled = await self.service.compile_document(
            self.user_id,
            created["id"],
            source_version_id=created["current_source_version_id"],
        )
        candidate = compiled["compiled_candidates"][0]

        self.service.delete_document(self.user_id, created["id"])

        self.assertFalse(
            any(
                row.get("id") == created["id"]
                for row in self.service.list_documents(self.user_id)
            )
        )
        with self.assertRaises(AgentRuleError) as missing:
            self.service.get_document(self.user_id, created["id"])
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(AgentRuleError) as cannot_activate:
            self.service.activate(
                self.user_id,
                created["id"],
                compiled_version_id=candidate["id"],
            )
        self.assertEqual(cannot_activate.exception.status_code, 404)
        with main.db.connection() as connection:
            tombstone = connection.execute(
                """
                SELECT deleted_at FROM agent_rule_documents
                WHERE id = ?
                """,
                (created["id"],),
            ).fetchone()
            self.assertIsNotNone(tombstone["deleted_at"])
            self.assertIsNotNone(
                connection.execute(
                    """
                    SELECT id FROM agent_rule_source_versions
                    WHERE id = ?
                    """,
                    (created["current_source_version_id"],),
                ).fetchone()
            )
            self.assertIsNotNone(
                connection.execute(
                    """
                    SELECT id FROM agent_compiled_rule_versions
                    WHERE id = ?
                    """,
                    (candidate["id"],),
                ).fetchone()
            )
        delete_audit = next(
            item for item in self.audits if item[1] == "agent_rule.delete"
        )
        self.assertEqual(
            delete_audit[5]["source_version_id"],
            created["current_source_version_id"],
        )
        self.assertEqual(
            delete_audit[5]["compiled_version_id"],
            candidate["id"],
        )
        self.assertEqual(
            delete_audit[5]["compiled_content_sha256"],
            candidate["content_sha256"],
        )

        replacement = self.service.create_document(
            self.user_id,
            name="可删除规则",
            source_document="同名的新规则。",
        )
        self.assertNotEqual(replacement["id"], created["id"])

    async def test_delete_rolls_back_when_transactional_audit_fails(self):
        created = self.service.create_document(
            self.user_id,
            name="删除审计原子性",
            source_document="审计失败时不能留下墓碑。",
        )

        def fail_audit(_connection, *_args):
            raise RuntimeError("audit unavailable")

        service = AgentRuleService(
            main.db.connection,
            compile_model=self.service.compile_model,
            audit=lambda *_args: None,
            audit_in_transaction=fail_audit,
        )

        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            service.delete_document(self.user_id, created["id"])

        with main.db.connection() as connection:
            document = connection.execute(
                """
                SELECT deleted_at
                FROM agent_rule_documents
                WHERE id = ?
                """,
                (created["id"],),
            ).fetchone()
        self.assertIsNotNone(document)
        self.assertIsNone(document["deleted_at"])

    async def test_production_delete_writes_audit_in_same_database(self):
        created = main.agent_rule_service.create_document(
            self.user_id,
            name="删除审计生产接线",
            source_document="验证生产服务使用事务内审计。",
        )

        main.agent_rule_service.delete_document(
            self.user_id,
            created["id"],
        )

        with main.db.connection() as connection:
            audit = connection.execute(
                """
                SELECT outcome, details_json
                FROM audit_log
                WHERE action = 'agent_rule.delete'
                  AND target_type = 'agent_rule_document'
                  AND target_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (created["id"],),
            ).fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit["outcome"], "success")
        self.assertEqual(
            json.loads(audit["details_json"])["source_version_id"],
            created["current_source_version_id"],
        )

    async def test_active_delete_is_forbidden_and_permissions_are_enforced(
        self,
    ):
        personal = self.service.create_document(
            self.user_id,
            name="个人删除权限",
            source_document="个人规则。",
        )
        compiled = await self.service.compile_document(
            self.user_id,
            personal["id"],
            source_version_id=personal["current_source_version_id"],
        )
        candidate_id = compiled["compiled_candidates"][0]["id"]
        self.service.activate(
            self.user_id,
            personal["id"],
            compiled_version_id=candidate_id,
        )
        with self.assertRaises(AgentRuleError) as active:
            self.service.delete_document(self.user_id, personal["id"])
        self.assertEqual(active.exception.code, "active_rule_delete_forbidden")
        self.assertEqual(active.exception.status_code, 409)
        self.assertEqual(
            self.service.get_document(self.user_id, personal["id"])[
                "active_compiled_version_id"
            ],
            candidate_id,
        )
        with self.assertRaises(AgentRuleError) as admin_denied:
            self.service.delete_document(
                self.admin_id,
                personal["id"],
                is_admin=True,
            )
        self.assertEqual(admin_denied.exception.status_code, 404)

        system = self.service.create_document(
            self.admin_id,
            name="系统删除权限",
            source_document="系统规则。",
            scope="system_default",
            is_admin=True,
        )
        with self.assertRaises(AgentRuleError) as member_denied:
            self.service.delete_document(self.user_id, system["id"])
        self.assertEqual(member_denied.exception.code, "administrator_required")
        self.service.delete_document(
            self.other_admin_id,
            system["id"],
            is_admin=True,
        )

    async def test_bulk_pagination_cannot_compile_or_reactivate(
        self,
    ):
        async def compile_model(_request):
            return {
                "content": json.dumps(deterministic_pagination_rule())
            }

        service = AgentRuleService(
            main.db.connection,
            compile_model=compile_model,
            audit=lambda *_args: None,
            audit_in_transaction=lambda _connection, *_args: None,
        )
        created = service.create_document(
            self.admin_id,
            name="系统分页规则",
            source_document="入口流水完整分页。",
            scope="system_default",
            is_admin=True,
        )
        compiled = await service.compile_document(
            self.admin_id,
            created["id"],
            source_version_id=created["current_source_version_id"],
            is_admin=True,
        )
        candidate = compiled["compiled_candidates"][0]
        self.assertEqual(candidate["status"], "invalid")
        self.assertIsNone(candidate["compiled_rule"])
        self.assertEqual(
            candidate["validation_errors"][0]["type"],
            "bulk_iteration_disabled",
        )

        historical_candidate_id = str(uuid.uuid4())
        historical_json = json.dumps(
            deterministic_pagination_rule(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with main.db.connection(write=True, immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_compiled_rule_versions (
                    id, document_id, source_version_id,
                    specification_version, status, content_sha256,
                    compiled_json, model_output, validation_errors_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    historical_candidate_id,
                    created["id"],
                    created["current_source_version_id"],
                    "chatraw-agent-rule-1.2",
                    "valid",
                    "f" * 64,
                    historical_json,
                    historical_json,
                    "[]",
                    "2026-07-31T00:00:00Z",
                ),
            )
        with self.assertRaises(AgentRuleError) as conflict:
            service.activate(
                self.admin_id,
                created["id"],
                compiled_version_id=historical_candidate_id,
                is_admin=True,
            )
        self.assertEqual(
            conflict.exception.code,
            "bulk_iteration_disabled",
        )

    async def test_duplicate_record_presentation_policy_is_rejected_per_scope(
        self,
    ):
        async def compile_model(_request):
            return {"content": json.dumps(record_presentation_rule())}

        service = AgentRuleService(
            main.db.connection,
            compile_model=compile_model,
            audit=lambda *_args: None,
            audit_in_transaction=lambda _connection, *_args: None,
        )
        candidates = []
        for index in range(2):
            created = service.create_document(
                self.admin_id,
                name=f"系统展示规则-{index}",
                source_document="业务记录默认总结。",
                scope="system_default",
                is_admin=True,
            )
            compiled = await service.compile_document(
                self.admin_id,
                created["id"],
                source_version_id=created["current_source_version_id"],
                is_admin=True,
            )
            candidates.append(
                (created["id"], compiled["compiled_candidates"][0]["id"])
            )
        service.activate(
            self.admin_id,
            candidates[0][0],
            compiled_version_id=candidates[0][1],
            is_admin=True,
        )

        with self.assertRaises(AgentRuleError) as conflict:
            service.activate(
                self.admin_id,
                candidates[1][0],
                compiled_version_id=candidates[1][1],
                is_admin=True,
            )
        self.assertEqual(
            conflict.exception.code,
            "record_presentation_rule_conflict",
        )
        self.assertIsNone(
            service.get_document(
                self.admin_id,
                candidates[1][0],
                is_admin=True,
            )["active_compiled_version_id"]
        )

    async def test_combined_system_and_personal_limit_is_fail_closed(self):
        system_candidates = []
        for index in range(9):
            created = self.service.create_document(
                self.admin_id,
                name=f"系统容量-{index}",
                source_document="系统执行规则。",
                scope="system_default",
                is_admin=True,
            )
            compiled = await self.service.compile_document(
                self.admin_id,
                created["id"],
                source_version_id=created["current_source_version_id"],
                is_admin=True,
            )
            system_candidates.append(
                (created["id"], compiled["compiled_candidates"][0]["id"])
            )
        for document_id, candidate_id in system_candidates:
            self.service.activate(
                self.admin_id,
                document_id,
                compiled_version_id=candidate_id,
                is_admin=True,
            )

        personal_candidates = []
        for index in range(2):
            created = self.service.create_document(
                self.user_id,
                name=f"个人容量-{index}",
                source_document="个人执行规则。",
            )
            compiled = await self.service.compile_document(
                self.user_id,
                created["id"],
                source_version_id=created["current_source_version_id"],
            )
            personal_candidates.append(
                (created["id"], compiled["compiled_candidates"][0]["id"])
            )
        self.service.activate(
            self.user_id,
            personal_candidates[0][0],
            compiled_version_id=personal_candidates[0][1],
        )
        with self.assertRaises(AgentRuleError) as full:
            self.service.activate(
                self.user_id,
                personal_candidates[1][0],
                compiled_version_id=personal_candidates[1][1],
            )
        self.assertEqual(full.exception.code, "too_many_active_rules")
        snapshots = self.service.active_snapshots(self.user_id)
        self.assertEqual(len(snapshots), 10)
        self.assertEqual(
            [item["scope"] for item in snapshots],
            ["system_default"] * 9 + ["personal"],
        )

    async def test_system_activation_cannot_overflow_existing_personal_rules(
        self,
    ):
        for index in range(10):
            created = self.service.create_document(
                self.user_id,
                name=f"既有个人容量-{index}",
                source_document="个人执行规则。",
            )
            compiled = await self.service.compile_document(
                self.user_id,
                created["id"],
                source_version_id=created["current_source_version_id"],
            )
            self.service.activate(
                self.user_id,
                created["id"],
                compiled_version_id=compiled[
                    "compiled_candidates"
                ][0]["id"],
            )

        system = self.service.create_document(
            self.admin_id,
            name="新增系统容量",
            source_document="系统执行规则。",
            scope="system_default",
            is_admin=True,
        )
        compiled_system = await self.service.compile_document(
            self.admin_id,
            system["id"],
            source_version_id=system["current_source_version_id"],
            is_admin=True,
        )
        with self.assertRaises(AgentRuleError) as full:
            self.service.activate(
                self.admin_id,
                system["id"],
                compiled_version_id=compiled_system[
                    "compiled_candidates"
                ][0]["id"],
                is_admin=True,
            )
        self.assertEqual(full.exception.code, "too_many_active_rules")
        self.assertIsNone(
            self.service.get_document(
                self.admin_id,
                system["id"],
                is_admin=True,
            )["active_compiled_version_id"]
        )
