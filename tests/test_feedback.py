"""
Feedback: a parent's message is saved for their family and emailed to Tally,
replies going to the parent. Students can't send it, and a failed email
never loses the message.
"""
from unittest import mock

import httpx

from api_support import as_
from database.db import SessionLocal
from database.models import Feedback, User
from services.email_service import EmailService

SMITH = as_("smith_parent")
BOB = as_("bob")


def _saved():
    db = SessionLocal()
    try:
        return db.query(Feedback).all()
    finally:
        db.close()


def _user_id(email):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).one().id
    finally:
        db.close()


def test_a_parent_sends_feedback(api, world):
    with mock.patch.object(EmailService, "send", return_value=True) as send:
        response = api.post("/feedback", json={"message": "  Love it!  "}, headers=SMITH)

    assert response.status_code == 201

    [row] = _saved()
    assert row.message == "Love it!"
    assert row.family_id == world.smith
    assert row.user_id == _user_id("smith_parent@x.test")

    to, subject, text = send.call_args.args
    assert to == "hello@tallyhomeschool.com"
    assert "Love it!" in text
    assert "smith_parent@x.test" in text
    assert send.call_args.kwargs["reply_to"] == "smith_parent@x.test"


def test_a_blank_message_is_refused(api):
    with mock.patch.object(EmailService, "send") as send:
        response = api.post("/feedback", json={"message": "   "}, headers=SMITH)

    assert response.status_code == 400
    assert response.json()["detail"] == "Please write a message."
    assert _saved() == []
    send.assert_not_called()


def test_students_cant_send_feedback(api):
    with mock.patch.object(EmailService, "send") as send:
        response = api.post("/feedback", json={"message": "hi"}, headers=BOB)

    assert response.status_code == 403
    assert _saved() == []
    send.assert_not_called()


def test_feedback_is_saved_even_if_the_email_fails(api, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")

    with mock.patch("services.email_service.httpx.post", side_effect=httpx.ConnectError("down")):
        response = api.post("/feedback", json={"message": "Still here"}, headers=SMITH)

    assert response.status_code == 201
    assert [row.message for row in _saved()] == ["Still here"]


def test_no_key_means_no_email(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with (
        mock.patch("services.email_service.get_optional_setting", return_value=None),
        mock.patch("services.email_service.httpx.post") as post,
    ):
        assert EmailService.send("a@x.test", "Hi", "Body") is False

    post.assert_not_called()


def test_the_email_goes_to_resend(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")

    with mock.patch(
        "services.email_service.httpx.post",
        return_value=httpx.Response(200, json={"id": "1"}),
    ) as post:
        assert EmailService.send("a@x.test", "Hi", "Body", reply_to="p@x.test") is True

    payload = post.call_args.kwargs["json"]
    assert payload["from"] == "tally <hello@tallyhomeschool.com>"
    assert payload["to"] == ["a@x.test"]
    assert payload["reply_to"] == "p@x.test"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"
