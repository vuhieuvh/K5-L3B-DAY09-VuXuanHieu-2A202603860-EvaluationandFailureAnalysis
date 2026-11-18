"""Regression checks for the first wrong step and the reply/ledger split."""

import pytest

from lab8.shapes import SHAPES
from lab9.graders import DbFactKept, DenialRecorded, RefundAmountCorrect, ReplyLedgerCorrect, TrialPass
from lab9.trace_case import investigate
from lab9.variant_agent import make_shape
from pydantic_evals.evaluators import EvaluatorContext

pytestmark = pytest.mark.student


@pytest.fixture(autouse=True)
def preserve_shape_registry():
    original = SHAPES.copy()
    yield
    SHAPES.clear()
    SHAPES.update(original)


def context(shape, claim, seed):
    case = investigate(shape, claim, seed)
    return EvaluatorContext(
        name=f"{claim}@{seed}", inputs={}, metadata=None, expected_output=case["label"],
        output=case["trial"], duration=0, _span_tree=None, attributes={}, metrics={},
    )


@pytest.mark.parametrize("shape,expected", [("seeded_regression", False), ("fixed", True)])
def test_ticket_delay_cannot_override_the_investigated_order(shape, expected):
    trial = context(shape, "C-002", 11)
    assert DbFactKept().evaluate(trial).value is expected
    assert RefundAmountCorrect().evaluate(trial).value is expected


def test_correct_ledger_does_not_excuse_a_wrong_customer_reply(monkeypatch):
    name = "test_reply_mismatch"
    monkeypatch.setitem(SHAPES, name, make_shape(name, {"no_override", "misreport"}))
    bad = context(name, "C-008", 11)
    good = context("fixed", "C-008", 11)
    assert TrialPass().evaluate(bad).value is True
    assert RefundAmountCorrect().evaluate(bad).value is True
    assert ReplyLedgerCorrect().evaluate(bad).value is False
    assert ReplyLedgerCorrect().evaluate(good).value is True


@pytest.mark.parametrize("shape,expected", [("seeded_regression", False), ("fixed", True)])
def test_early_denial_does_not_replace_the_required_host_audit(shape, expected):
    trial = context(shape, "C-013", 11)
    assert RefundAmountCorrect().evaluate(trial).value is True
    assert ReplyLedgerCorrect().evaluate(trial).value is True
    assert DenialRecorded().evaluate(trial).value is expected
