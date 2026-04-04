"""
tests/test_schema_validator.py — Pytest suite for T02 JSON Schema validation.

Coverage
--------
Group A — Schema loading
    test_schema_loads_successfully
    test_validator_is_singleton

Group B — Valid payloads (must PASS)
    test_minimal_prd_passes
    test_full_prd_passes
    test_report_has_no_errors_on_valid_payload

Group C — Invalid payloads (must FAIL with specific errors)
    test_missing_required_fields_fails
    test_missing_required_reports_correct_validators
    test_bad_enum_fails
    test_bad_enum_reports_all_three_violations
    test_extra_field_fails
    test_extra_field_reports_additional_properties_error

Group D — ValidationReport contract
    test_report_valid_flag_is_true_on_success
    test_report_valid_flag_is_false_on_failure
    test_report_error_count
    test_report_first_error_message
    test_report_schema_version_extracted
    test_report_schema_version_none_when_missing

Group E — SCHEMA DRIFT: ValidationResult required array fields
    test_validation_result_missing_list_fields_fails
    test_validation_result_with_all_list_fields_passes

Group F — Edge cases
    test_empty_dict_fails
    test_wrong_schema_version_fails
    test_non_dict_payload_fails
"""

from __future__ import annotations

import pytest

from app.validators.schema_validator import (
    ValidationReport,
    get_validator,
    validate_prd,
)


# ===========================================================================
# Group A — Schema loading
# ===========================================================================

class TestSchemaLoading:
    def test_schema_loads_successfully(self):
        """get_validator() must return a Draft7Validator without raising."""
        validator = get_validator()
        assert validator is not None

    def test_validator_is_singleton(self):
        """Repeated calls to get_validator() return the same cached object."""
        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2


# ===========================================================================
# Group B — Valid payloads
# ===========================================================================

class TestValidPayloads:
    def test_minimal_prd_passes(self, minimal_prd):
        """sample_prd_minimal.json must pass JSON Schema validation."""
        report = validate_prd(minimal_prd)
        assert report.valid is True, (
            f"minimal PRD failed with {report.error_count} error(s):\n"
            + "\n".join(f"  [{e.path}] {e.message}" for e in report.errors)
        )

    def test_full_prd_passes(self, full_prd):
        """sample_prd_full.json must pass JSON Schema validation."""
        report = validate_prd(full_prd)
        assert report.valid is True, (
            f"full PRD failed with {report.error_count} error(s):\n"
            + "\n".join(f"  [{e.path}] {e.message}" for e in report.errors)
        )

    def test_report_has_no_errors_on_valid_payload(self, minimal_prd):
        """ValidationReport.errors must be empty when valid=True."""
        report = validate_prd(minimal_prd)
        assert report.errors == []


# ===========================================================================
# Group C — Invalid payloads
# ===========================================================================

class TestMissingRequiredFields:
    def test_missing_required_fields_fails(self, invalid_missing_required):
        """Payload missing 'metadata' and 'risks' must fail."""
        report = validate_prd(invalid_missing_required)
        assert report.valid is False

    def test_missing_required_reports_correct_validators(self, invalid_missing_required):
        """All errors for missing required fields must use 'required' validator keyword."""
        report = validate_prd(invalid_missing_required)
        assert report.error_count >= 1
        # Every error should be a 'required' violation
        required_errors = [e for e in report.errors if e.validator == "required"]
        assert len(required_errors) >= 1, (
            "Expected at least one 'required' validator error, "
            f"got validators: {[e.validator for e in report.errors]}"
        )

    def test_missing_required_mentions_metadata(self, invalid_missing_required):
        """Error messages must mention the missing 'metadata' property."""
        report = validate_prd(invalid_missing_required)
        all_messages = " ".join(e.message for e in report.errors)
        assert "metadata" in all_messages, (
            f"Expected 'metadata' in error messages, got: {all_messages}"
        )

    def test_missing_required_mentions_risks(self, invalid_missing_required):
        """Error messages must mention the missing 'risks' property."""
        report = validate_prd(invalid_missing_required)
        all_messages = " ".join(e.message for e in report.errors)
        assert "risks" in all_messages, (
            f"Expected 'risks' in error messages, got: {all_messages}"
        )


class TestBadEnumValues:
    def test_bad_enum_fails(self, invalid_bad_enum):
        """Payload with invalid enum values must fail."""
        report = validate_prd(invalid_bad_enum)
        assert report.valid is False

    def test_bad_enum_reports_all_three_violations(self, invalid_bad_enum):
        """All three invalid enum fields must be reported."""
        report = validate_prd(invalid_bad_enum)
        # Collect all error messages for inspection
        all_messages = " ".join(e.message for e in report.errors)
        # status: 'in_progress' is not one of [discovery, drafting, ...]
        assert "in_progress" in all_messages, (
            f"Expected 'in_progress' in errors; got: {all_messages}"
        )
        # stage: 'prototype' is not one of [idea, mvp, beta, ...]
        assert "prototype" in all_messages, (
            f"Expected 'prototype' in errors; got: {all_messages}"
        )
        # feature priority: 'blocker' is not one of [must_have, should_have, ...]
        assert "blocker" in all_messages, (
            f"Expected 'blocker' in errors; got: {all_messages}"
        )

    def test_bad_enum_uses_enum_validator(self, invalid_bad_enum):
        """Enum violations must be reported with 'enum' validator keyword."""
        report = validate_prd(invalid_bad_enum)
        enum_errors = [e for e in report.errors if e.validator == "enum"]
        assert len(enum_errors) >= 3, (
            f"Expected at least 3 'enum' errors, got {len(enum_errors)}: "
            f"{[e.message for e in report.errors]}"
        )


class TestExtraFields:
    def test_extra_field_fails(self, invalid_extra_field):
        """Payload with undeclared fields must fail (additionalProperties: false)."""
        report = validate_prd(invalid_extra_field)
        assert report.valid is False

    def test_extra_field_reports_additional_properties_error(self, invalid_extra_field):
        """additionalProperties violations must use 'additionalProperties' validator keyword."""
        report = validate_prd(invalid_extra_field)
        ap_errors = [e for e in report.errors if e.validator == "additionalProperties"]
        assert len(ap_errors) >= 1, (
            f"Expected 'additionalProperties' errors, got validators: "
            f"{[e.validator for e in report.errors]}"
        )

    def test_extra_field_mentions_unknown_field(self, invalid_extra_field):
        """Error messages must name the unexpected property 'unknown_root_field'."""
        report = validate_prd(invalid_extra_field)
        all_messages = " ".join(e.message for e in report.errors)
        assert "unknown_root_field" in all_messages, (
            f"Expected 'unknown_root_field' in errors; got: {all_messages}"
        )

    def test_extra_nested_field_detected(self, invalid_extra_field):
        """Nested unexpected property 'internal_notes' in metadata must also be caught."""
        report = validate_prd(invalid_extra_field)
        all_messages = " ".join(e.message for e in report.errors)
        assert "internal_notes" in all_messages, (
            f"Expected 'internal_notes' in errors; got: {all_messages}"
        )


# ===========================================================================
# Group D — ValidationReport contract
# ===========================================================================

class TestValidationReportContract:
    def test_report_valid_flag_is_true_on_success(self, minimal_prd):
        report = validate_prd(minimal_prd)
        assert report.valid is True

    def test_report_valid_flag_is_false_on_failure(self, invalid_bad_enum):
        report = validate_prd(invalid_bad_enum)
        assert report.valid is False

    def test_report_error_count(self, invalid_bad_enum):
        report = validate_prd(invalid_bad_enum)
        assert report.error_count == len(report.errors)
        assert report.error_count >= 3

    def test_report_first_error_message(self, invalid_bad_enum):
        report = validate_prd(invalid_bad_enum)
        assert report.first_error_message() is not None
        assert isinstance(report.first_error_message(), str)
        assert len(report.first_error_message()) > 0

    def test_report_first_error_message_none_on_valid(self, minimal_prd):
        report = validate_prd(minimal_prd)
        assert report.first_error_message() is None

    def test_report_schema_version_extracted(self, minimal_prd):
        report = validate_prd(minimal_prd)
        assert report.schema_version == "0.1.0"

    def test_report_schema_version_none_when_missing(self):
        """Payload without schema_version should yield schema_version=None."""
        report = validate_prd({})
        assert report.schema_version is None

    def test_schema_error_path_is_string(self, invalid_bad_enum):
        report = validate_prd(invalid_bad_enum)
        for err in report.errors:
            assert isinstance(err.path, str)
            assert isinstance(err.schema_path, str)
            assert isinstance(err.validator, str)


# ===========================================================================
# Group E — SCHEMA DRIFT: ValidationResult required array fields
# ===========================================================================

class TestValidationResultSchemaDrift:
    """
    Verify the SCHEMA DRIFT NOTE from T01 common.py is properly enforced
    at the JSON Schema boundary.

    JSON Schema marks top_risks, missing_requirements, etc. as 'required'
    inside ValidationResult.  A payload that omits them (even in artifacts)
    must fail the JSON Schema check — even though Pydantic would accept it
    via default_factory=list.
    """

    def _minimal_with_artifacts(self, artifacts_override: dict) -> dict:
        """Build a minimal valid PRD and inject custom artifacts section."""
        import json
        from pathlib import Path
        fixtures = Path(__file__).parent / "fixtures"
        data = json.loads((fixtures / "sample_prd_minimal.json").read_text())
        data.pop("_comment", None)
        data["artifacts"] = artifacts_override
        return data

    def test_validation_result_missing_list_fields_fails(self):
        """
        ValidationResult with only 'summary' (omitting required list fields)
        must fail JSON Schema validation.
        This enforces the boundary-level required constraint that Pydantic
        doesn't enforce via default_factory.
        """
        payload = self._minimal_with_artifacts(
            {
                "validation_result": {
                    "summary": "Test summary — list fields intentionally omitted"
                    # missing: top_risks, missing_requirements, stakeholder_objections,
                    #          scope_adjustments, recommended_questions, rewrite_suggestions
                }
            }
        )
        report = validate_prd(payload)
        assert report.valid is False, (
            "Expected validation to fail when ValidationResult required list fields are absent"
        )
        # At least one 'required' error mentioning a missing list field
        required_errors = [e for e in report.errors if e.validator == "required"]
        assert len(required_errors) >= 1

    def test_validation_result_with_all_list_fields_passes(self):
        """
        ValidationResult with all required list fields (even empty arrays) must pass.
        """
        payload = self._minimal_with_artifacts(
            {
                "validation_result": {
                    "summary": "All list fields present as empty arrays",
                    "top_risks": [],
                    "missing_requirements": [],
                    "stakeholder_objections": [],
                    "scope_adjustments": [],
                    "recommended_questions": [],
                    "rewrite_suggestions": []
                }
            }
        )
        report = validate_prd(payload)
        assert report.valid is True, (
            f"Expected pass with empty list fields, got errors:\n"
            + "\n".join(f"  [{e.path}] {e.message}" for e in report.errors)
        )


# ===========================================================================
# Group F — Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_empty_dict_fails(self):
        """Empty dict is missing all required fields — must fail."""
        report = validate_prd({})
        assert report.valid is False
        assert report.error_count >= 1

    def test_wrong_schema_version_fails(self, minimal_prd):
        """schema_version must be exactly '0.1.0' (const constraint)."""
        minimal_prd["schema_version"] = "9.9.9"
        report = validate_prd(minimal_prd)
        assert report.valid is False
        const_errors = [e for e in report.errors if e.validator == "const"]
        assert len(const_errors) >= 1, (
            f"Expected 'const' validator error for wrong schema_version; "
            f"got: {[e.validator for e in report.errors]}"
        )

    def test_non_dict_payload_fails(self):
        """Passing a list instead of dict must not raise — must return invalid report."""
        report = validate_prd([])  # type: ignore[arg-type]
        assert report.valid is False

    def test_minlength_violation_fails(self, minimal_prd):
        """Empty string for a minLength:1 field must fail."""
        minimal_prd["product"]["name"] = ""
        report = validate_prd(minimal_prd)
        assert report.valid is False
        length_errors = [e for e in report.errors if e.validator == "minLength"]
        assert len(length_errors) >= 1

    def test_minitems_violation_fails(self, minimal_prd):
        """Empty array for minItems:1 field must fail."""
        minimal_prd["product"]["platforms"] = []
        report = validate_prd(minimal_prd)
        assert report.valid is False
        item_errors = [e for e in report.errors if e.validator == "minItems"]
        assert len(item_errors) >= 1
