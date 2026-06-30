"""Action plane — turning insight into progress.

These tools don't just read; they *do*. In the demo they record a proposed action
into the RunContext so the cockpit can surface it as a card the human approves.
Go-live swap: wire each to Power Automate / Graph / your CRM to actually send.
"""
from __future__ import annotations

from typing import Annotated, Callable

from pydantic import Field

from .skins.schema import Skin
from .planes.base import RunContext


def make_action_tools(skin: Skin, ctx: RunContext) -> list[Callable[..., str]]:
    def draft_outreach(
        audience: Annotated[str, Field(description="Who the message is for, e.g. 'available EMTs near Zone 4'.")],
        message: Annotated[str, Field(description="The ready-to-send message text.")],
    ) -> str:
        """Draft an outreach message (SMS/email) to a group. Use when the user wants to reach people."""
        ctx.propose("outreach", "✉️", f"Draft outreach → {audience}", message)
        return f"Drafted outreach to {audience}. Awaiting the coordinator's approval to send."

    def create_task(
        title: Annotated[str, Field(description="Short task title.")],
        assignee: Annotated[str, Field(description="Who should own the task.")],
        due: Annotated[str, Field(description="When it's due, e.g. 'tonight 8 PM'.")],
    ) -> str:
        """Create a follow-up task/assignment. Use to capture a concrete next step for someone."""
        ctx.propose("task", "✅", f"Task: {title}", f"Assignee: {assignee} · Due: {due}")
        return f"Task '{title}' staged for {assignee} (due {due}). Awaiting approval."

    def trigger_workflow(
        name: Annotated[str, Field(description="Workflow name, e.g. 'dispatch confirmation'.")],
        summary: Annotated[str, Field(description="What the workflow will do.")],
    ) -> str:
        """Trigger an operational workflow (e.g. dispatch, callout cascade). Use for multi-step automation."""
        ctx.propose("workflow", "⚙️", f"Workflow: {name}", summary)
        return f"Workflow '{name}' staged. Awaiting approval to run."

    return [draft_outreach, create_task, trigger_workflow]
