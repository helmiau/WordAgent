from langsmith import utils as langsmith_utils

from app.services.agent import agent


def test_importing_agent_keeps_test_tracing_disabled():
    assert agent._langsmith_enabled is False
    assert langsmith_utils.tracing_is_enabled() is False
