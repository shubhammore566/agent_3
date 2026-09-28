"""Headless Streamlit checks for: connect AWS from chat, remembered per GitHub login."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class FakeUser:
    def __init__(self, login):
        self.login = login


class FakeClient:
    def get_repo(self, name):
        raise RuntimeError("not needed in this test")


def new_app(login=None):
    at = AppTest.from_file(APP, default_timeout=60)
    if login:
        at.session_state["gh_user"] = FakeUser(login)
        at.session_state["gh_client"] = FakeClient()
        at.session_state["github_access_token"] = "ghp_fake"
    return at


def say(at, text):
    at.chat_input[0].set_value(text).run()
    assert not at.exception, [e.value for e in at.exception]
    return at.session_state["messages"][-1]["content"]


def test_chat_connect_resume_and_remember(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_STATE_DIR", str(tmp_path))

    at = new_app("tester")
    at.run()
    at.session_state["pending_confirmation"] = {"type": "deploy_aws_ec2", "repo": "tester/app", "port": "", "ref": "main"}
    reply = say(at, "yes")
    assert "Account ID here in the chat" in reply          # asks in chat, not "open the sidebar"

    reply = say(at, "816600798815")
    assert "AWS account: `816600798815`" in reply and "About to deploy" in reply   # resumes with approval
    at.run()
    saved = json.loads((tmp_path / "aws_prefs.json").read_text())
    assert saved["tester"]["account_id"] == "816600798815"

    again = new_app("tester")                               # new session / page reload
    again.run()
    assert again.session_state["aws_oidc_role_arn"].endswith("816600798815:role/GitHubAgentDeploymentRole")

    other = new_app("someone_else")                         # another user never inherits it
    other.run()
    assert other.session_state["aws_oidc_role_arn"] == ""


def test_access_key_is_refused_and_random_numbers_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_STATE_DIR", str(tmp_path))
    at = new_app("tester2")
    at.run()
    assert "Access Key" in say(at, "my aws key AKIAABCDEFGHIJKLMNOP")
    say(at, "order 123456789012 please")
    assert not at.session_state["aws_oidc_role_arn"]
