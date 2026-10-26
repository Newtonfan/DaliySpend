"""``flask`` CLI helpers."""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from .extensions import db
from .models import User
from .services.seed import bootstrap_new_user


@click.command("init-db")
@click.option("--drop", is_flag=True, help="先删除所有表再重建（会丢数据）")
@with_appcontext
def init_db(drop: bool) -> None:
    """Create every table from the models (development shortcut)."""
    if drop:
        db.drop_all()
        click.confirm("已删除全部表，确认重建？", abort=True)
    db.create_all()
    click.echo("数据库表已就绪。")


@click.group("user")
def user_cli() -> None:
    """用户管理。"""


@user_cli.command("create")
@click.option("--email", prompt=True)
@click.option("--display-name", prompt="显示名称")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_user(email: str, display_name: str, password: str) -> None:
    """Create a user together with the default categories and accounts."""
    normalized = email.strip().lower()
    if db.session.query(User.id).filter_by(email=normalized).first():
        raise click.ClickException(f"用户已存在：{normalized}")
    user = User(email=normalized, display_name=display_name.strip() or normalized)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    bootstrap_new_user(user)
    click.echo(f"已创建用户 {user.email}（id={user.id}）。")


@user_cli.command("list")
@with_appcontext
def list_users() -> None:
    """List existing users."""
    for user in db.session.query(User).order_by(User.id).all():
        click.echo(f"{user.id}\t{user.email}\t{user.display_name}")


def register_cli(app: Flask) -> None:
    app.cli.add_command(init_db)
    app.cli.add_command(user_cli)
