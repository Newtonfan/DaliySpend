"""Pure helpers of the Oracle provisioning script (no database needed)."""

from __future__ import annotations

import re

import create_oracle_users as provision

URL_SAFE = re.compile(r"^[A-Za-z0-9_.~-]+$")
SPECIALS = set("_-.")


def test_generated_password_meets_oracle_and_url_rules():
    for _ in range(20):
        password = provision.generate_password()
        assert len(password) == 24
        # Safe both as an Oracle password and inside a URL's userinfo section.
        assert URL_SAFE.match(password), password
        assert any(char.isdigit() for char in password)
        assert any(char.isalpha() for char in password)
        assert SPECIALS & set(password)


def test_generated_passwords_are_unique():
    passwords = {provision.generate_password() for _ in range(50)}
    assert len(passwords) == 50


def test_normalise_connect_accepts_ezconnect_and_prefixed_forms():
    assert provision.normalise_connect("") == "//localhost:1521/FREEPDB1"
    assert (
        provision.normalise_connect("localhost:1521/FREEPDB1") == "//localhost:1521/FREEPDB1"
    )
    assert provision.normalise_connect("//other:1521/FREE") == "//other:1521/FREE"


def test_build_url_uses_service_name():
    url = provision.build_url("dailyspend", "p-w_d", "localhost:1521/FREEPDB1")
    assert url == "oracle+oracledb://dailyspend:p-w_d@localhost:1521/?service_name=FREEPDB1"


def test_build_url_without_service_name():
    url = provision.build_url("u", "p", "localhost:1521")
    assert url == "oracle+oracledb://u:p@localhost:1521"


def test_env_block_is_appendable():
    url = provision.build_url("u", "p", "localhost:1521/FREEPDB1")
    block = provision.env_block(url)
    assert block.startswith("# Oracle")
    assert f"DS_DATABASE_URL={url}\n" in block
