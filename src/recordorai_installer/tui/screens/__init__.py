"""Wizard screens — one module per step.

Each screen subclasses :class:`textual.screen.Screen` and accepts a
:class:`recordorai_installer.tui.state.WizardState` in its constructor.
On submit, the screen mutates ``self.state`` and pushes the next
screen onto the app stack.
"""
