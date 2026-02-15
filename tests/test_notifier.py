"""Tests for the notifier module (email notifications)."""

import json
import os
from unittest.mock import patch, MagicMock, call

import pytest

import config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_proposals():
    """Return a list of sample proposal dicts for testing."""
    return [
        {
            "job_uid": "~abc12345",
            "proposal_text": "I have extensive experience building AI chatbots with LangChain.",
            "match_score": 85,
        },
        {
            "job_uid": "~def67890",
            "proposal_text": "Your NLP pipeline project is a great fit for my skills.",
            "match_score": 62,
        },
    ]


@pytest.fixture
def sample_stats():
    """Return a sample monitor_stats dict."""
    return {
        "jobs_matched": 10,
        "proposals_generated": 5,
    }


@pytest.fixture
def email_cfg():
    """Return a realistic email configuration dict."""
    return {
        "enabled": True,
        "smtp": {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "test@gmail.com",
        },
        "notifications": {
            "recipient": "recipient@example.com",
            "max_proposals_per_email": 10,
            "min_proposals_to_send": 1,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateProposalHtml:
    """Tests for generate_proposal_html()."""

    def test_generate_html_contains_proposal_cards(self, sample_proposals, sample_stats):
        """HTML output should contain proposal info, scores, and Upwork job links."""
        with patch("notifier.load_config", return_value={
            "notifications": {"max_proposals_per_email": 10},
        }):
            from notifier import generate_proposal_html

            html_output = generate_proposal_html(sample_proposals, sample_stats)

        # Contains the job uid fragment in the title (first 8 chars)
        assert "~abc1234" in html_output
        assert "~def6789" in html_output

        # Contains Upwork job links
        assert "https://www.upwork.com/jobs/~abc12345" in html_output
        assert "https://www.upwork.com/jobs/~def67890" in html_output

        # Contains match scores
        assert "85" in html_output
        assert "62" in html_output

        # Contains stats section values
        assert "10" in html_output  # jobs_matched
        assert "5" in html_output   # proposals_generated

        # Contains structural HTML markers (pipeline summary labels)
        assert "Scraped" in html_output
        assert "Matched" in html_output
        assert "Proposals" in html_output
        assert "Generated Proposals" in html_output

    def test_html_escaping_prevents_injection(self, sample_stats):
        """Proposals with <script> tags must be HTML-escaped to prevent XSS."""
        malicious_proposals = [
            {
                "job_uid": '<script>alert("xss")</script>',
                "proposal_text": '<script>document.cookie</script> Legit proposal text.',
                "match_score": 50,
            },
        ]

        with patch("notifier.load_config", return_value={
            "notifications": {"max_proposals_per_email": 10},
        }):
            from notifier import generate_proposal_html

            html_output = generate_proposal_html(malicious_proposals, sample_stats)

        # Raw <script> tags must NOT appear in the output
        assert "<script>" not in html_output

        # Escaped versions must be present
        assert "&lt;script&gt;" in html_output

        # The job URL should also have the uid escaped
        assert "alert" in html_output  # text is still there, just escaped
        assert "&lt;script&gt;alert" in html_output


class TestSendViaSmtp:
    """Tests for send_via_smtp()."""

    def test_smtp_send_with_mock(self, email_cfg, monkeypatch):
        """SMTP connection should call starttls, login, and sendmail."""
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "fake-app-password")

        mock_server = MagicMock()
        mock_smtp_cls = MagicMock()
        # __enter__ returns the mock server so `with smtplib.SMTP(...) as server:` works
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("notifier.smtplib.SMTP", mock_smtp_cls):
            from notifier import send_via_smtp

            result = send_via_smtp("Test Subject", "<h1>Hello</h1>", email_cfg)

        assert result is True

        # SMTP was called with the right host/port
        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587)

        # The context-managed server had starttls, login, and sendmail called
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@gmail.com", "fake-app-password")
        mock_server.sendmail.assert_called_once()
        call_args = mock_server.sendmail.call_args[0]
        assert call_args[0] == "test@gmail.com"
        assert call_args[1] == ["recipient@example.com"]

    def test_smtp_missing_password_returns_false(self, email_cfg, monkeypatch):
        """send_via_smtp should return False when GMAIL_APP_PASSWORD is not set."""
        monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

        from notifier import send_via_smtp

        result = send_via_smtp("Test Subject", "<h1>Hello</h1>", email_cfg)

        assert result is False


class TestSaveEmailFallback:
    """Tests for save_email_fallback()."""

    def test_fallback_saves_html_file(self, tmp_path, sample_proposals, sample_stats, monkeypatch):
        """Fallback should create an HTML file and a corresponding status JSON."""
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)

        from notifier import save_email_fallback

        result_path = save_email_fallback(
            "Test Subject",
            "<h1>Proposals</h1>",
            sample_proposals,
            sample_stats,
        )

        # Returns a path string
        assert isinstance(result_path, str)
        assert result_path.endswith(".html")

        # HTML file was created and contains the body
        assert os.path.exists(result_path)
        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<h1>Proposals</h1>" in content

        # Corresponding status JSON was created
        status_path = result_path.replace(".html", "_status.json")
        assert os.path.exists(status_path)
        with open(status_path, "r", encoding="utf-8") as f:
            status_data = json.load(f)
        assert status_data["subject"] == "Test Subject"
        assert status_data["proposals_count"] == 2
        assert status_data["delivery_status"] == "fallback_file_saved"
        assert status_data["monitor_stats"] == sample_stats


class TestSendNotification:
    """Tests for the orchestrator send_notification()."""

    def test_dry_run_skips_sending(self, sample_proposals, sample_stats):
        """dry_run=True should return True immediately without loading config or sending."""
        from notifier import send_notification

        # No patches needed -- dry_run short-circuits before any config/SMTP access
        result = send_notification(sample_proposals, sample_stats, dry_run=True)

        assert result is True

    def test_disabled_email_returns_true(self, sample_proposals, sample_stats):
        """When email is disabled in config, send_notification should return True (no error)."""
        disabled_cfg = {
            "enabled": False,
            "smtp": {},
            "notifications": {},
        }

        with patch("notifier.load_email_config", return_value=disabled_cfg):
            from notifier import send_notification

            result = send_notification(sample_proposals, sample_stats, dry_run=False)

        assert result is True
