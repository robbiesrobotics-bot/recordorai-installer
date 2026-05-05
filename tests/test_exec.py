"""Tests for recordorai_installer.core.exec_."""

from __future__ import annotations

from recordorai_installer.core.exec_ import EventType, ExecEvent, execute
from recordorai_installer.core.plan import Plan, Step


def _capture():
    events: list[ExecEvent] = []
    return events, lambda e: events.append(e)


class TestExecuteHappyPath:
    def test_runs_every_step_in_order_and_emits_events(self):
        order: list[str] = []

        plan = Plan(
            steps=[
                Step(kind="config", title="step-a", do=lambda: order.append("a")),
                Step(kind="config", title="step-b", do=lambda: order.append("b")),
                Step(kind="config", title="step-c", do=lambda: order.append("c")),
            ]
        )
        events, sink = _capture()
        result = execute(plan, on_event=sink)

        assert result.success is True
        assert len(result.completed_steps) == 3
        assert order == ["a", "b", "c"]

        types = [e.type for e in events]
        assert types[0] == EventType.PLAN_START
        assert types[-1] == EventType.PLAN_OK
        assert types.count(EventType.STEP_START) == 3
        assert types.count(EventType.STEP_OK) == 3

    def test_pure_data_steps_with_no_do_callback_pass_through(self):
        plan = Plan(steps=[Step(kind="config", title="empty")])
        result = execute(plan)
        assert result.success is True

    def test_verify_step_with_passes_true_succeeds(self):
        plan = Plan(
            steps=[
                Step(
                    kind="verify",
                    title="precheck",
                    metadata={"passes": True},
                ),
            ]
        )
        result = execute(plan)
        assert result.success is True


class TestExecuteRollback:
    def test_failing_step_triggers_reverse_order_undo(self):
        history: list[str] = []

        def make_do(name):
            def _do():
                history.append(f"do:{name}")

            return _do

        def make_undo(name):
            def _undo():
                history.append(f"undo:{name}")

            return _undo

        def boom():
            history.append("do:c-attempt")
            raise RuntimeError("synthetic")

        plan = Plan(
            steps=[
                Step(
                    kind="config",
                    title="a",
                    do=make_do("a"),
                    undo=make_undo("a"),
                ),
                Step(
                    kind="config",
                    title="b",
                    do=make_do("b"),
                    undo=make_undo("b"),
                ),
                Step(kind="config", title="c", do=boom, undo=make_undo("c")),
                Step(
                    kind="config",
                    title="d",
                    do=make_do("d"),
                    undo=make_undo("d"),
                ),
            ]
        )
        result = execute(plan)

        assert result.success is False
        assert isinstance(result.error, RuntimeError)
        # a + b ran successfully, c failed mid-flight, d never started.
        assert "do:a" in history
        assert "do:b" in history
        assert "do:c-attempt" in history
        assert "do:d" not in history
        # Undo runs in reverse order for completed steps only.
        undo_idx_a = history.index("undo:a")
        undo_idx_b = history.index("undo:b")
        assert undo_idx_b < undo_idx_a  # b undone first (reverse)
        assert "undo:c" not in history  # c never completed → not undone
        assert "undo:d" not in history

    def test_undo_failures_are_logged_but_dont_stop_rollback(self):
        events, sink = _capture()
        plan = Plan(
            steps=[
                Step(
                    kind="config",
                    title="a",
                    do=lambda: None,
                    undo=lambda: (_ for _ in ()).throw(RuntimeError("undo crashed")),
                ),
                Step(
                    kind="config",
                    title="b",
                    do=lambda: (_ for _ in ()).throw(RuntimeError("step crashed")),
                ),
            ]
        )
        result = execute(plan, on_event=sink)

        assert result.success is False
        # Rollback emitted ROLLBACK_STEP for the (failed) undo with an error message.
        rollback_steps = [e for e in events if e.type == EventType.ROLLBACK_STEP]
        assert len(rollback_steps) == 1
        assert rollback_steps[0].error is not None


class TestVerifySoftFail:
    def test_verify_passes_false_aborts_by_default(self):
        plan = Plan(
            steps=[
                Step(kind="verify", title="check", metadata={"passes": False}),
                Step(kind="config", title="never-runs"),
            ]
        )
        result = execute(plan, allow_warn=False)
        assert result.success is False
        assert result.failed_step.title == "check"

    def test_verify_passes_false_with_allow_warn_continues(self):
        ran_b = []
        plan = Plan(
            steps=[
                Step(kind="verify", title="check", metadata={"passes": False}),
                Step(kind="config", title="b", do=lambda: ran_b.append(True)),
            ]
        )
        result = execute(plan, allow_warn=True)
        assert result.success is True
        assert ran_b == [True]
