"""Slack incident card filtering for the investigation feed."""

from app.services.slack_client import (
    is_incident_feed_channel,
    qualifies_for_incident_feed,
)
from app.services.slack_types import SlackThreadRecord


def test_incident_feed_channel_name_rules():
    assert is_incident_feed_channel("incident") is True
    assert is_incident_feed_channel("#incident") is True
    assert is_incident_feed_channel("incident-payments") is True
    assert is_incident_feed_channel("incidents") is False
    assert is_incident_feed_channel("eng-alerts") is False
    assert is_incident_feed_channel("general") is False


def test_qualifies_for_incident_feed_requires_channel_and_signal():
    assert (
        qualifies_for_incident_feed(
            SlackThreadRecord(
                channel_id="C1",
                channel_name="incident",
                thread_ts="1",
                parent_text="SEV1 checkout outage",
            )
        )
        is True
    )
    assert (
        qualifies_for_incident_feed(
            SlackThreadRecord(
                channel_id="C1",
                channel_name="incident",
                thread_ts="2",
                parent_text="lunch at 1?",
            )
        )
        is False
    )
    assert (
        qualifies_for_incident_feed(
            SlackThreadRecord(
                channel_id="C2",
                channel_name="eng",
                thread_ts="3",
                parent_text="prod outage",
                is_incident_channel=True,
            )
        )
        is False
    )
    assert (
        qualifies_for_incident_feed(
            SlackThreadRecord(
                channel_id="C1",
                channel_name="incident",
                thread_ts="5",
                parent_text="incidental deploy chatter",
            )
        )
        is False
    )
