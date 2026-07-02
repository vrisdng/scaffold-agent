"""Policy evaluation for proposed agent actions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from maikit_core.agent_spec import PolicyConfig


class PolicyDecision(BaseModel):
    allowed_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    approval_required_actions: list[str] = Field(default_factory=list)
    unknown_actions: list[str] = Field(default_factory=list)
    requires_human_approval: bool


def evaluate_policy(actions: list[str], policy: PolicyConfig) -> PolicyDecision:
    """Classifies proposed actions against the configured policy."""
    allowed: list[str] = []
    blocked: list[str] = []
    approval_required: list[str] = []
    unknown: list[str] = []

    for action in actions:
        if action in policy.blocked_actions:
            blocked.append(action)
        elif action in policy.approval_required:
            approval_required.append(action)
        elif action in policy.allowed_actions:
            allowed.append(action)
        else:
            unknown.append(action)

    return PolicyDecision(
        allowed_actions=allowed,
        blocked_actions=blocked,
        approval_required_actions=approval_required,
        unknown_actions=unknown,
        requires_human_approval=bool(blocked or approval_required),
    )
