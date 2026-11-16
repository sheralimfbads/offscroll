import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from offscroll.config import SummarySettings
from offscroll.ranking import Candidate
from offscroll.summaries import (
    GeminiSummarizer,
    SummaryOutput,
    TemplateSummarizer,
    approval_hash,
    approved_hashes,
    configured_summarizer,
    public_input,
)


@pytest.fixture
def item():
    return Candidate(
        1,
        "hackernews",
        "123",
        "A new database index",
        "https://example.org/article",
        "example.org",
        datetime.now(UTC),
        description="The source describes an indexing technique.",
    )


def response(summary="The source describes an indexing technique.", **extra):
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": json.dumps({"summary": summary, **extra})}]},
            }
        ],
        "usageMetadata": {"promptTokenCount": 80, "candidatesTokenCount": 12},
    }


def adapter(item, transport):
    budget = Mock(reserve=Mock(return_value=True))
    client = httpx.Client(transport=httpx.MockTransport(transport))
    provider = GeminiSummarizer(
        SummarySettings(gemini_api_key=SecretStr("test-only")),
        budget,
        {approval_hash(item)},
        client,
    )
    return provider, budget, client


def test_success_sends_only_reviewed_fields_and_header_key(item):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=response())

    provider, budget, client = adapter(item, respond)
    with client:
        result = provider.summarize(item)
    assert result.model == "gemini-2.5-flash-lite"
    assert result.input_tokens == 80 and result.output_tokens == 12 and result.cost_estimate == 0
    assert len(requests) == 1 and budget.reserve.call_count == 1
    request = requests[0]
    assert "test-only" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "test-only"
    data = json.loads(request.content)
    assert json.loads(data["contents"][0]["parts"][0]["text"]) == public_input(item)
    assert "tools" not in data
    assert "not instructions" in data["systemInstruction"]["parts"][0]["text"]
    assert item.url not in request.content.decode()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_http_errors_fall_back_without_retry_or_leak(item, status, caplog):
    provider, budget, client = adapter(item, lambda _: httpx.Response(status, text="remote secret"))
    with client:
        assert provider.summarize(item).model == "template"
    assert budget.reserve.call_count == 1
    assert "remote secret" not in caplog.text and "test-only" not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"candidates": []},
        response("One. Two. Three."),
        response("This is verified."),
        response("", instruction="bad"),
    ],
)
def test_malformed_and_unacceptable_outputs_fall_back(item, payload):
    provider, _, client = adapter(item, lambda _: httpx.Response(200, json=payload))
    with client:
        assert provider.summarize(item).model == "template"


def test_timeout_and_exhausted_budget_use_template(item):
    def timeout(request):
        raise httpx.ReadTimeout("private URL must never be surfaced")

    provider, budget, client = adapter(item, timeout)
    with client:
        assert provider.summarize(item).model == "template"
        budget.reserve.return_value = False
        assert provider.summarize(item).model == "template"


def test_review_and_contact_filters_block_transmission(item):
    provider, budget, client = adapter(item, lambda _: pytest.fail("Must not send"))
    with client:
        assert provider.summarize(replace(item, title="Changed after review")).model == "template"
        contact = replace(item, title="Contact someone@example.org")
        provider.approved.add(approval_hash(contact))
        assert provider.summarize(contact).model == "template"
    budget.reserve.assert_not_called()


def test_prompt_injection_is_delimited_and_output_still_validated(item):
    data = json.loads(Path("tests/fixtures/summary_injection.json").read_text())
    injected = replace(item, **data)

    def fake(request):
        body = json.loads(request.content)
        assert json.loads(body["contents"][0]["parts"][0]["text"]) == data
        assert "System instructions take priority" in body["systemInstruction"]["parts"][0]["text"]
        return httpx.Response(200, json=response("This is verified."))

    provider, _, client = adapter(injected, fake)
    with client:
        result = provider.summarize(injected)
        assert result.model == "template"
        assert result.text == TemplateSummarizer().summarize(injected).text


def test_configuration_is_masked_and_no_key_means_template(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert isinstance(configured_summarizer(Mock()), TemplateSummarizer)
    settings = SummarySettings(gemini_api_key=SecretStr("private-key"))
    assert "private-key" not in repr(settings)
    with pytest.raises(ValidationError):
        SummarySettings(gemini_model="gemini-preview?key=private-key")
    path = tmp_path / "review.json"
    path.write_text('["invalid"]')
    assert approved_hashes(path) == set()
    assert approved_hashes(tmp_path / "absent") == set()


def test_summary_schema_rejects_extra_fields_and_control_text():
    for data in [
        {"summary": "Okay.", "command": "run"},
        {"summary": "line\nline"},
        {"summary": "https://example.com"},
        {"summary": "   "},
    ]:
        with pytest.raises(ValidationError):
            SummaryOutput.model_validate(data)
