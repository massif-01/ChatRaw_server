"""Versioned user rule documents and deterministic compiled-rule validation."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TARGET_MODULE_ID = "chatraw.agent"
SPECIFICATION_VERSION = "chatraw-agent-rule-1.2"
MAX_SOURCE_DOCUMENT_BYTES = 128 * 1024
MAX_COMPILED_RULE_BYTES = 64 * 1024
MAX_ACTIVE_RULES_PER_TASK = 10
PERSONAL_SCOPE = "personal"
SYSTEM_DEFAULT_SCOPE = "system_default"
RULE_SCOPES = frozenset({PERSONAL_SCOPE, SYSTEM_DEFAULT_SCOPE})
_RULE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AgentRuleError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class RuleTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all: list[str] = Field(default_factory=list, max_length=20)
    any: list[str] = Field(default_factory=list, max_length=20)
    none: list[str] = Field(default_factory=list, max_length=20)


class RuleIteration(BaseModel):
    """Legacy v1.0 model-guidance iteration contract."""

    model_config = ConfigDict(extra="forbid")

    cursor_argument: str = Field(min_length=1, max_length=128)
    start: int
    step: int = Field(ge=1, le=1000000)
    page_size_argument: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )
    page_size: int | None = Field(default=None, ge=1, le=1000000)
    stop_when: Literal[
        "empty_result",
        "short_page",
        "described_condition",
    ]
    stop_description: str = Field(default="", max_length=1000)
    max_calls: int = Field(default=100, ge=1, le=256)

    @model_validator(mode="after")
    def validate_pairing(self):
        if (self.page_size_argument is None) != (self.page_size is None):
            raise ValueError(
                "page_size_argument and page_size must appear together"
            )
        if (
            self.stop_when == "described_condition"
            and not self.stop_description.strip()
        ):
            raise ValueError(
                "described_condition requires stop_description"
            )
        return self


class RuleToolPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selector: str = Field(min_length=1, max_length=1000)
    names: list[str] = Field(default_factory=list, max_length=20)
    argument_defaults: dict[str, Any] = Field(default_factory=dict)
    argument_constants: dict[str, Any] = Field(default_factory=dict)
    iteration: RuleIteration | None = None

    @model_validator(mode="after")
    def validate_arguments(self):
        overlap = set(self.argument_defaults) & set(
            self.argument_constants
        )
        if overlap:
            raise ValueError(
                "arguments cannot be both defaults and constants"
            )
        return self


class ExecutionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=50, ge=1, le=100)
    when: RuleTrigger = Field(default_factory=RuleTrigger)
    instructions: list[str] = Field(min_length=1, max_length=20)
    tools: list[RuleToolPolicy] = Field(default_factory=list, max_length=20)
    response_requirements: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_id(self):
        if not _RULE_ID.fullmatch(self.id):
            raise ValueError("rule id format is invalid")
        return self


class RecordPresentationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applies_to: Literal["structured_business_records"]
    default_mode: Literal["summary", "records"]
    identifier_fields: list[str] = Field(
        default_factory=list,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_identifier_fields(self):
        normalized = [value.strip() for value in self.identifier_fields]
        if (
            any(not value or len(value) > 128 for value in normalized)
            or len(normalized) != len(set(normalized))
        ):
            raise ValueError(
                "identifier_fields must contain unique non-empty field names"
            )
        self.identifier_fields = normalized
        return self


class DeterministicPaginationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    cursor_argument: str = Field(min_length=1, max_length=128)
    start: int
    step: int = Field(ge=1, le=1000000)
    page_size_argument: str = Field(min_length=1, max_length=128)
    page_size: int = Field(ge=1, le=1000000)
    stop_when: Literal["empty_result"]
    max_pages: int = Field(default=100, ge=1, le=1024)


class CompiledRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1", "1.2"]
    kind: Literal[
        "execution",
        "record_presentation",
        "deterministic_pagination",
    ] | None = None
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    execution_rules: list[ExecutionRule] = Field(
        default_factory=list,
        max_length=50,
    )
    record_presentation: RecordPresentationPolicy | None = None
    deterministic_pagination: (
        DeterministicPaginationPolicy | None
    ) = None
    clarification_rules: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_contract(self):
        has_legacy_iteration = any(
            tool.iteration is not None
            for rule in self.execution_rules
            for tool in rule.tools
        )
        if self.schema_version == "1.0":
            if (
                self.kind is not None
                or self.record_presentation is not None
                or self.deterministic_pagination is not None
                or not self.execution_rules
            ):
                raise ValueError(
                    "schema 1.0 requires execution_rules and forbids "
                    "kind and record_presentation"
                )
        elif self.kind == "execution":
            if (
                self.record_presentation is not None
                or self.deterministic_pagination is not None
                or not self.execution_rules
                or has_legacy_iteration
            ):
                raise ValueError(
                    "execution rules require execution_rules and forbid "
                    "record_presentation, deterministic_pagination, and "
                    "legacy iteration"
                )
        elif self.kind == "record_presentation":
            if (
                self.record_presentation is None
                or self.deterministic_pagination is not None
                or self.execution_rules
                or (
                    self.schema_version == "1.1"
                    and self.record_presentation.identifier_fields
                )
            ):
                raise ValueError(
                    "record_presentation rules require the typed policy "
                    "and forbid incompatible fields"
                )
        elif self.kind == "deterministic_pagination":
            if (
                self.schema_version != "1.2"
                or self.deterministic_pagination is None
                or self.record_presentation is not None
                or self.execution_rules
            ):
                raise ValueError(
                    "deterministic_pagination requires schema 1.2 and its "
                    "typed policy, and forbids other rule payloads"
                )
        else:
            raise ValueError(
                "schema 1.1 and 1.2 require a supported kind"
            )

        identifiers = [rule.id for rule in self.execution_rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("execution rule ids must be unique")
        return self

    def uses_bulk_iteration(self) -> bool:
        """Return whether this historical rule can multiply tool calls."""

        return (
            self.kind == "deterministic_pagination"
            or any(
                tool.iteration is not None
                for rule in self.execution_rules
                for tool in rule.tools
            )
        )


COMPILED_RULE_JSON_SCHEMA = CompiledRule.model_json_schema()

COMPILER_SPECIFICATION = f"""
You compile a user's Source Document into a ChatRaw Compiled Rule.

Return exactly one JSON object. Do not return Markdown or commentary.
The JSON must conform exactly to this schema:
{json.dumps(COMPILED_RULE_JSON_SCHEMA, ensure_ascii=False, separators=(",", ":"))}

Compilation rules:
1. Emit schema_version "1.2" and exactly one explicit kind. Use
   kind "execution" for operational guidance. Use
   kind "record_presentation" only for a presentation-default policy over
   structured business records. Never emit kind
   "deterministic_pagination".
2. Preserve only requirements stated by the Source Document. Do not invent
   business facts, tool names, field names, dates, permissions, or defaults.
3. Convert operational instructions into ordered execution_rules. A rule's
   when fields describe when it applies; instructions describe required work.
4. Use tools[].selector for a semantic tool description. Add tools[].names
   only when the Source Document states exact tool names.
5. Put fixed arguments in argument_constants and fallback values in
   argument_defaults.
6. Never create a loop, pagination contract, repeated-call instruction, or
   legacy tools[].iteration. If the Source asks for full detail traversal,
   preserve the unsupported request in clarification_rules; do not translate
   it into executable guidance.
7. If the Source Document is ambiguous or missing required runtime input,
   preserve that uncertainty in clarification_rules. Never guess.
8. Never create rules that grant tool permissions, bypass confirmations,
   change security policy, expose secrets, or override execution budgets.
9. The compiled rule is guidance for a general Agent. It must not contain
   executable code, shell commands, templates, or model-control instructions.
10. A record_presentation rule must contain only record_presentation and
    clarification_rules. It must not duplicate the policy into
    execution_rules and must never change query scope, tool choice, pagination,
    calculation, file generation, or non-business conversation behavior.
11. identifier_fields may list exact record identifier field names only when
    the Source Document states them. Do not invent identifier fields.
12. Rules cannot request interactive full-detail retrieval or an export.
    Those operations belong to a separate bulk workflow, not Agent chat.
""".strip()


class AgentRuleService:
    def __init__(
        self,
        connection: Callable[..., Any],
        *,
        compile_model: Callable[
            [dict[str, Any]], Awaitable[dict[str, Any]]
        ],
        audit: Callable[..., None],
        audit_in_transaction: Callable[..., None],
    ):
        self.connection = connection
        self.compile_model = compile_model
        self.audit = audit
        self.audit_in_transaction = audit_in_transaction

    @staticmethod
    def _validate_source(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AgentRuleError(
                "invalid_source_document",
                "Source Document is required",
            )
        if len(value.encode("utf-8")) > MAX_SOURCE_DOCUMENT_BYTES:
            raise AgentRuleError(
                "source_document_too_large",
                "Source Document is too large",
                413,
            )
        return value

    @staticmethod
    def _document_summary(
        row: Any,
        *,
        editable: bool,
    ) -> dict[str, Any]:
        keys = set(row.keys())
        return {
            "id": row["id"],
            "name": row["name"],
            "target_module_id": row["target_module_id"],
            "scope": row["scope"],
            "editable": editable,
            "active": row["active_compiled_version_id"] is not None,
            "current_source_version_id": row[
                "current_source_version_id"
            ],
            "active_compiled_version_id": row[
                "active_compiled_version_id"
            ],
            "active_source_version_id": (
                row["active_source_version_id"]
                if "active_source_version_id" in keys
                else None
            ),
            "active_specification_version": (
                row["active_specification_version"]
                if "active_specification_version" in keys
                else None
            ),
            "active_content_sha256": (
                row["active_content_sha256"]
                if "active_content_sha256" in keys
                else None
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _require_scope(scope: str, *, is_admin: bool) -> str:
        if scope not in RULE_SCOPES:
            raise AgentRuleError(
                "invalid_rule_scope",
                "Rule scope is invalid",
            )
        if scope == SYSTEM_DEFAULT_SCOPE and not is_admin:
            raise AgentRuleError(
                "administrator_required",
                "Administrator permission required",
                403,
            )
        return scope

    @staticmethod
    def _authorize_document(
        row: Any,
        actor_user_id: str,
        *,
        is_admin: bool,
    ) -> Any:
        if row is None:
            raise AgentRuleError(
                "rule_document_not_found",
                "Rule document was not found",
                404,
            )
        if row["scope"] == SYSTEM_DEFAULT_SCOPE:
            if not is_admin:
                raise AgentRuleError(
                    "administrator_required",
                    "Administrator permission required",
                    403,
                )
        elif row["owner_user_id"] != actor_user_id:
            raise AgentRuleError(
                "rule_document_not_found",
                "Rule document was not found",
                404,
            )
        return row

    def _authorized_document(
        self,
        actor_user_id: str,
        document_id: str,
        *,
        is_admin: bool,
    ):
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND target_module_id = ?
                  AND deleted_at IS NULL
                """,
                (document_id, TARGET_MODULE_ID),
            ).fetchone()
        return self._authorize_document(
            row,
            actor_user_id,
            is_admin=is_admin,
        )

    def list_documents(
        self,
        actor_user_id: str,
        *,
        is_admin: bool = False,
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT documents.*,
                       versions.source_version_id
                         AS active_source_version_id,
                       versions.specification_version
                         AS active_specification_version,
                       versions.content_sha256
                         AS active_content_sha256
                FROM agent_rule_documents AS documents
                LEFT JOIN agent_compiled_rule_versions AS versions
                  ON versions.id = documents.active_compiled_version_id
                WHERE documents.target_module_id = ?
                  AND documents.deleted_at IS NULL
                  AND (
                    documents.scope = 'system_default'
                    OR (
                      documents.scope = 'personal'
                      AND documents.owner_user_id = ?
                    )
                  )
                ORDER BY
                  CASE documents.scope
                    WHEN 'system_default' THEN 0
                    ELSE 1
                  END,
                  documents.updated_at DESC,
                  documents.name,
                  documents.id
                """,
                (TARGET_MODULE_ID, actor_user_id),
            ).fetchall()
        summaries = []
        for row in rows:
            summary = self._document_summary(
                row,
                editable=(
                    is_admin
                    if row["scope"] == SYSTEM_DEFAULT_SCOPE
                    else row["owner_user_id"] == actor_user_id
                ),
            )
            if (
                row["scope"] == SYSTEM_DEFAULT_SCOPE
                and not is_admin
            ):
                summary = {
                    key: summary[key]
                    for key in (
                        "name",
                        "scope",
                        "editable",
                        "active",
                        "active_compiled_version_id",
                        "active_specification_version",
                        "active_content_sha256",
                    )
                }
            summaries.append(summary)
        return summaries

    def get_document(
        self,
        actor_user_id: str,
        document_id: str,
        *,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        document = self._authorized_document(
            actor_user_id,
            document_id,
            is_admin=is_admin,
        )
        with self.connection() as connection:
            sources = connection.execute(
                """
                SELECT id, version_number, source_document,
                       content_sha256, created_at
                FROM agent_rule_source_versions
                WHERE document_id = ?
                ORDER BY version_number DESC
                """,
                (document_id,),
            ).fetchall()
            candidates = connection.execute(
                """
                SELECT id, source_version_id, specification_version,
                       status, content_sha256, compiled_json,
                       model_output, validation_errors_json, created_at
                FROM agent_compiled_rule_versions
                WHERE document_id = ?
                ORDER BY created_at DESC
                """,
                (document_id,),
            ).fetchall()
        result = self._document_summary(document, editable=True)
        result["source_versions"] = [dict(row) for row in sources]
        result["compiled_candidates"] = [
            {
                **dict(row),
                "compiled_rule": (
                    json.loads(row["compiled_json"])
                    if row["compiled_json"]
                    else None
                ),
                "validation_errors": json.loads(
                    row["validation_errors_json"]
                ),
            }
            for row in candidates
        ]
        for candidate in result["compiled_candidates"]:
            candidate.pop("compiled_json")
            candidate.pop("validation_errors_json")
        return result

    def create_document(
        self,
        actor_user_id: str,
        *,
        name: str,
        source_document: str,
        scope: str = PERSONAL_SCOPE,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        name = name.strip() if isinstance(name, str) else ""
        if not name or len(name) > 200:
            raise AgentRuleError(
                "invalid_rule_name",
                "Rule document name is invalid",
            )
        source_document = self._validate_source(source_document)
        scope = self._require_scope(scope, is_admin=is_admin)
        document_id = str(uuid.uuid4())
        source_version_id = str(uuid.uuid4())
        now = _utc_now()
        try:
            with self.connection(write=True, immediate=True) as connection:
                connection.execute(
                    """
                    INSERT INTO agent_rule_documents (
                        id, owner_user_id, target_module_id, name,
                        scope,
                        current_source_version_id,
                        active_compiled_version_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        document_id,
                        actor_user_id,
                        TARGET_MODULE_ID,
                        name,
                        scope,
                        source_version_id,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO agent_rule_source_versions (
                        id, document_id, version_number, source_document,
                        content_sha256, created_at
                    ) VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    (
                        source_version_id,
                        document_id,
                        source_document,
                        _sha256(source_document),
                        now,
                    ),
                )
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise AgentRuleError(
                    "rule_name_conflict",
                    "A rule document with this name already exists",
                    409,
                ) from None
            raise
        self.audit(
            actor_user_id,
            "agent_rule.create",
            "agent_rule_document",
            document_id,
            "success",
            {
                "scope": scope,
                "source_version_id": source_version_id,
                "source_content_sha256": _sha256(source_document),
            },
        )
        return self.get_document(
            actor_user_id,
            document_id,
            is_admin=is_admin,
        )

    def update_source(
        self,
        actor_user_id: str,
        document_id: str,
        *,
        expected_source_version_id: str,
        source_document: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        source_document = self._validate_source(source_document)
        source_version_id = str(uuid.uuid4())
        now = _utc_now()
        with self.connection(write=True, immediate=True) as connection:
            document = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND target_module_id = ?
                  AND deleted_at IS NULL
                """,
                (document_id, TARGET_MODULE_ID),
            ).fetchone()
            document = self._authorize_document(
                document,
                actor_user_id,
                is_admin=is_admin,
            )
            if (
                document["current_source_version_id"]
                != expected_source_version_id
            ):
                raise AgentRuleError(
                    "source_version_conflict",
                    "Source Document has changed; reload before saving",
                    409,
                )
            next_version = connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM agent_rule_source_versions
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO agent_rule_source_versions (
                    id, document_id, version_number, source_document,
                    content_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_version_id,
                    document_id,
                    next_version,
                    source_document,
                    _sha256(source_document),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET current_source_version_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (source_version_id, now, document_id),
            )
        self.audit(
            actor_user_id,
            "agent_rule.source.update",
            "agent_rule_document",
            document_id,
            "success",
            {
                "scope": document["scope"],
                "source_version_id": source_version_id,
                "source_content_sha256": _sha256(source_document),
            },
        )
        return self.get_document(
            actor_user_id,
            document_id,
            is_admin=is_admin,
        )

    @staticmethod
    def _validated_candidate(
        model_output: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        try:
            raw = json.loads(model_output)
        except json.JSONDecodeError as error:
            return None, [
                {
                    "type": "invalid_json",
                    "message": str(error),
                }
            ]
        try:
            compiled = CompiledRule.model_validate(raw)
        except Exception as error:
            details = (
                error.errors(include_context=False)
                if hasattr(error, "errors")
                else [{"type": "validation_error", "message": str(error)}]
            )
            return None, details
        if compiled.schema_version != "1.2":
            return None, [
                {
                    "type": "outdated_compiled_rule_schema",
                    "message": (
                        "New compiler output must use schema_version 1.2"
                    ),
                }
            ]
        if compiled.uses_bulk_iteration():
            return None, [
                {
                    "type": "bulk_iteration_disabled",
                    "message": (
                        "Bulk pagination and repeated tool-call rules are "
                        "disabled in fallback mode"
                    ),
                }
            ]
        normalized = compiled.model_dump(mode="json", exclude_none=True)
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > MAX_COMPILED_RULE_BYTES:
            return None, [
                {
                    "type": "compiled_rule_too_large",
                    "message": "Compiled Rule is too large",
                }
            ]
        return normalized, []

    async def compile_document(
        self,
        actor_user_id: str,
        document_id: str,
        *,
        source_version_id: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        document = self._authorized_document(
            actor_user_id,
            document_id,
            is_admin=is_admin,
        )
        with self.connection() as connection:
            source = connection.execute(
                """
                SELECT * FROM agent_rule_source_versions
                WHERE id = ? AND document_id = ?
                """,
                (source_version_id, document_id),
            ).fetchone()
        if source is None:
            raise AgentRuleError(
                "source_version_not_found",
                "Source Document version was not found",
                404,
            )
        request = {
            "profile": "agent-compiler",
            "messages": [
                {"role": "system", "content": COMPILER_SPECIFICATION},
                {
                    "role": "user",
                    "content": (
                        "Source Document:\n"
                        f"{source['source_document']}"
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 8192,
            "timeout_seconds": 600,
        }
        completion = await self.compile_model(request)
        model_output = completion.get("content")
        if not isinstance(model_output, str):
            raise AgentRuleError(
                "invalid_compiler_response",
                "Compiler model returned invalid content",
                502,
            )
        if len(model_output.encode("utf-8")) > MAX_COMPILED_RULE_BYTES:
            compiled = None
            validation_errors = [
                {
                    "type": "compiler_output_too_large",
                    "message": "Compiler model output is too large",
                }
            ]
            model_output = model_output.encode("utf-8")[
                :MAX_COMPILED_RULE_BYTES
            ].decode("utf-8", errors="ignore")
        else:
            compiled, validation_errors = self._validated_candidate(
                model_output
            )
        candidate_id = str(uuid.uuid4())
        now = _utc_now()
        normalized_json = (
            json.dumps(
                compiled,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if compiled is not None
            else None
        )
        content_digest = _sha256(normalized_json or model_output)
        with self.connection(write=True, immediate=True) as connection:
            current_document = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND target_module_id = ?
                  AND deleted_at IS NULL
                """,
                (document_id, TARGET_MODULE_ID),
            ).fetchone()
            self._authorize_document(
                current_document,
                actor_user_id,
                is_admin=is_admin,
            )
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
                    candidate_id,
                    document_id,
                    source_version_id,
                    SPECIFICATION_VERSION,
                    "valid" if compiled is not None else "invalid",
                    content_digest,
                    normalized_json,
                    model_output,
                    json.dumps(
                        validation_errors,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    now,
                ),
            )
        self.audit(
            actor_user_id,
            "agent_rule.compile",
            "agent_rule_document",
            document_id,
            "success" if compiled is not None else "invalid",
            {
                "source_version_id": source_version_id,
                "candidate_id": candidate_id,
                "specification_version": SPECIFICATION_VERSION,
                "scope": document["scope"],
                "content_sha256": content_digest,
            },
        )
        return self.get_document(
            actor_user_id,
            document["id"],
            is_admin=is_admin,
        )

    @staticmethod
    def _is_record_presentation(compiled_json: str | None) -> bool:
        if not compiled_json:
            return False
        try:
            compiled = json.loads(compiled_json)
        except json.JSONDecodeError:
            return False
        return (
            isinstance(compiled, dict)
            and compiled.get("schema_version") in {"1.1", "1.2"}
            and compiled.get("kind") == "record_presentation"
            and isinstance(compiled.get("record_presentation"), dict)
        )

    @staticmethod
    def _pagination_tool_name(
        compiled_json: str | None,
    ) -> str | None:
        if not compiled_json:
            return None
        try:
            compiled = json.loads(compiled_json)
        except json.JSONDecodeError:
            return None
        pagination = (
            compiled.get("deterministic_pagination")
            if isinstance(compiled, dict)
            else None
        )
        if (
            compiled.get("schema_version") != "1.2"
            or compiled.get("kind") != "deterministic_pagination"
            or not isinstance(pagination, dict)
        ):
            return None
        tool_name = pagination.get("tool_name")
        return tool_name if isinstance(tool_name, str) else None

    @classmethod
    def _validate_active_policy_conflicts(
        cls,
        connection: Any,
        document: Any,
    ) -> None:
        if document["scope"] == SYSTEM_DEFAULT_SCOPE:
            rows = connection.execute(
                """
                SELECT versions.compiled_json
                FROM agent_rule_documents AS documents
                JOIN agent_compiled_rule_versions AS versions
                  ON versions.id = documents.active_compiled_version_id
                WHERE documents.target_module_id = ?
                  AND documents.scope = 'system_default'
                  AND documents.deleted_at IS NULL
                  AND versions.status = 'valid'
                """,
                (TARGET_MODULE_ID,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT versions.compiled_json
                FROM agent_rule_documents AS documents
                JOIN agent_compiled_rule_versions AS versions
                  ON versions.id = documents.active_compiled_version_id
                WHERE documents.target_module_id = ?
                  AND documents.scope = 'personal'
                  AND documents.owner_user_id = ?
                  AND documents.deleted_at IS NULL
                  AND versions.status = 'valid'
                """,
                (TARGET_MODULE_ID, document["owner_user_id"]),
            ).fetchall()
        if (
            sum(
                cls._is_record_presentation(row["compiled_json"])
                for row in rows
            )
            > 1
        ):
            raise AgentRuleError(
                "record_presentation_rule_conflict",
                (
                    "Only one active record-presentation rule is allowed "
                    "for this scope"
                ),
                409,
            )
        pagination_tools = [
            tool_name
            for row in rows
            if (
                tool_name := cls._pagination_tool_name(
                    row["compiled_json"]
                )
            )
        ]
        if len(pagination_tools) != len(set(pagination_tools)):
            raise AgentRuleError(
                "deterministic_pagination_rule_conflict",
                (
                    "Only one active deterministic-pagination rule per "
                    "tool is allowed for this scope"
                ),
                409,
            )

    @staticmethod
    def _active_scope_count(
        connection: Any,
        scope: str,
        *,
        owner_user_id: str | None = None,
    ) -> int:
        owner_filter = ""
        parameters: list[Any] = [TARGET_MODULE_ID, scope]
        if owner_user_id is not None:
            owner_filter = " AND documents.owner_user_id = ?"
            parameters.append(owner_user_id)
        row = connection.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM agent_rule_documents AS documents
            JOIN agent_compiled_rule_versions AS versions
              ON versions.id = documents.active_compiled_version_id
            WHERE documents.target_module_id = ?
              AND documents.scope = ?
              AND documents.deleted_at IS NULL
              AND versions.status = 'valid'
              {owner_filter}
            """,
            parameters,
        ).fetchone()
        return int(row["count"])

    @classmethod
    def _validate_active_capacity(
        cls,
        connection: Any,
        document: Any,
    ) -> None:
        system_count = cls._active_scope_count(
            connection,
            SYSTEM_DEFAULT_SCOPE,
        )
        if system_count > MAX_ACTIVE_RULES_PER_TASK:
            raise AgentRuleError(
                "too_many_active_rules",
                "Too many active Agent rules",
                409,
            )
        if document["scope"] == PERSONAL_SCOPE:
            personal_count = cls._active_scope_count(
                connection,
                PERSONAL_SCOPE,
                owner_user_id=document["owner_user_id"],
            )
            if (
                system_count + personal_count
                > MAX_ACTIVE_RULES_PER_TASK
            ):
                raise AgentRuleError(
                    "too_many_active_rules",
                    "Too many active Agent rules",
                    409,
                )
            return

        rows = connection.execute(
            """
            SELECT documents.owner_user_id, COUNT(*) AS count
            FROM agent_rule_documents AS documents
            JOIN agent_compiled_rule_versions AS versions
              ON versions.id = documents.active_compiled_version_id
            WHERE documents.target_module_id = ?
              AND documents.scope = 'personal'
              AND documents.deleted_at IS NULL
              AND versions.status = 'valid'
            GROUP BY documents.owner_user_id
            """,
            (TARGET_MODULE_ID,),
        ).fetchall()
        if any(
            system_count + int(row["count"])
            > MAX_ACTIVE_RULES_PER_TASK
            for row in rows
        ):
            raise AgentRuleError(
                "too_many_active_rules",
                (
                    "Activating this system default would exceed the "
                    "per-task Agent rule limit for at least one user"
                ),
                409,
            )

    def activate(
        self,
        actor_user_id: str,
        document_id: str,
        *,
        compiled_version_id: str | None,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        with self.connection(write=True, immediate=True) as connection:
            document = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND target_module_id = ?
                  AND deleted_at IS NULL
                """,
                (document_id, TARGET_MODULE_ID),
            ).fetchone()
            document = self._authorize_document(
                document,
                actor_user_id,
                is_admin=is_admin,
            )
            candidate = None
            if compiled_version_id is not None:
                candidate = connection.execute(
                    """
                    SELECT * FROM agent_compiled_rule_versions
                    WHERE id = ? AND document_id = ?
                    """,
                    (compiled_version_id, document_id),
                ).fetchone()
                if candidate is None:
                    raise AgentRuleError(
                        "compiled_rule_not_found",
                        "Compiled Rule candidate was not found",
                        404,
                    )
                if (
                    candidate["status"] != "valid"
                    or not candidate["compiled_json"]
                ):
                    raise AgentRuleError(
                        "compiled_rule_invalid",
                        "Only a valid Compiled Rule can be activated",
                        409,
                    )
                try:
                    compiled_candidate = CompiledRule.model_validate_json(
                        candidate["compiled_json"]
                    )
                except Exception:
                    raise AgentRuleError(
                        "compiled_rule_invalid",
                        "Only a valid Compiled Rule can be activated",
                        409,
                    ) from None
                if compiled_candidate.uses_bulk_iteration():
                    raise AgentRuleError(
                        "bulk_iteration_disabled",
                        (
                            "Bulk pagination and repeated tool-call rules "
                            "are disabled in fallback mode"
                        ),
                        409,
                    )
                if (
                    document["scope"] == SYSTEM_DEFAULT_SCOPE
                    and candidate["source_version_id"]
                    != document["current_source_version_id"]
                ):
                    raise AgentRuleError(
                        "system_rule_candidate_stale",
                        (
                            "A system-default candidate must be compiled "
                            "from the current Source Document version"
                        ),
                        409,
                    )
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET active_compiled_version_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (compiled_version_id, _utc_now(), document_id),
            )
            if compiled_version_id is not None:
                self._validate_active_policy_conflicts(
                    connection,
                    document,
                )
                self._validate_active_capacity(connection, document)
        self.audit(
            actor_user_id,
            (
                "agent_rule.activate"
                if compiled_version_id is not None
                else "agent_rule.deactivate"
            ),
            "agent_rule_document",
            document_id,
            "success",
            {
                "scope": document["scope"],
                "compiled_version_id": compiled_version_id,
                "source_version_id": (
                    candidate["source_version_id"]
                    if candidate is not None
                    else None
                ),
                "content_sha256": (
                    candidate["content_sha256"]
                    if candidate is not None
                    else None
                ),
            },
        )
        return self.get_document(
            actor_user_id,
            document_id,
            is_admin=is_admin,
        )

    def active_snapshots(
        self,
        actor_user_id: str,
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT documents.id AS document_id,
                       documents.name,
                       versions.id AS compiled_version_id,
                       versions.source_version_id,
                       versions.specification_version,
                       versions.content_sha256,
                       documents.scope
                FROM agent_rule_documents AS documents
                JOIN agent_compiled_rule_versions AS versions
                  ON versions.id =
                     documents.active_compiled_version_id
                WHERE documents.target_module_id = ?
                  AND documents.deleted_at IS NULL
                  AND (
                    documents.scope = 'system_default'
                    OR (
                      documents.scope = 'personal'
                      AND documents.owner_user_id = ?
                    )
                  )
                  AND versions.status = 'valid'
                ORDER BY
                  CASE documents.scope
                    WHEN 'system_default' THEN 0
                    ELSE 1
                  END,
                  documents.updated_at,
                  documents.id
                LIMIT ?
                """,
                (
                    TARGET_MODULE_ID,
                    actor_user_id,
                    MAX_ACTIVE_RULES_PER_TASK + 1,
                ),
            ).fetchall()
        if len(rows) > MAX_ACTIVE_RULES_PER_TASK:
            raise AgentRuleError(
                "too_many_active_rules",
                "Too many active Agent rules",
                409,
            )
        return [dict(row) for row in rows]

    def delete_document(
        self,
        actor_user_id: str,
        document_id: str,
        *,
        is_admin: bool = False,
    ) -> None:
        now = _utc_now()
        with self.connection(write=True, immediate=True) as connection:
            document = connection.execute(
                """
                SELECT documents.*,
                       sources.version_number AS source_version_number,
                       sources.content_sha256 AS source_content_sha256,
                       versions.id AS last_compiled_version_id,
                       versions.source_version_id
                         AS last_compiled_source_version_id,
                       versions.specification_version,
                       versions.content_sha256
                         AS last_compiled_content_sha256
                FROM agent_rule_documents AS documents
                JOIN agent_rule_source_versions AS sources
                  ON sources.id = documents.current_source_version_id
                LEFT JOIN agent_compiled_rule_versions AS versions
                  ON versions.id = (
                    SELECT candidate.id
                    FROM agent_compiled_rule_versions AS candidate
                    WHERE candidate.document_id = documents.id
                    ORDER BY candidate.created_at DESC, candidate.id DESC
                    LIMIT 1
                  )
                WHERE documents.id = ?
                  AND documents.target_module_id = ?
                  AND documents.deleted_at IS NULL
                """,
                (document_id, TARGET_MODULE_ID),
            ).fetchone()
            document = self._authorize_document(
                document,
                actor_user_id,
                is_admin=is_admin,
            )
            if document["active_compiled_version_id"] is not None:
                raise AgentRuleError(
                    "active_rule_delete_forbidden",
                    "Deactivate the Agent rule before deleting it",
                    409,
                )
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET deleted_at = ?, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (now, now, document_id),
            )
            self.audit_in_transaction(
                connection,
                actor_user_id,
                "agent_rule.delete",
                "agent_rule_document",
                document_id,
                "success",
                {
                    "scope": document["scope"],
                    "source_version_id": document[
                        "current_source_version_id"
                    ],
                    "source_version_number": document[
                        "source_version_number"
                    ],
                    "source_content_sha256": document[
                        "source_content_sha256"
                    ],
                    "compiled_version_id": document[
                        "last_compiled_version_id"
                    ],
                    "compiled_source_version_id": document[
                        "last_compiled_source_version_id"
                    ],
                    "specification_version": document[
                        "specification_version"
                    ],
                    "compiled_content_sha256": document[
                        "last_compiled_content_sha256"
                    ],
                },
            )
