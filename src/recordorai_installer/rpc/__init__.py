"""JSON-RPC server bridging the Tauri front-end to the Python core.

The Tauri shell spawns ``python -m recordorai_installer --rpc`` as a
subprocess and talks JSON-RPC 2.0 over stdio. Each line on stdin is
one JSON-RPC request; each line on stdout is one JSON-RPC response or
notification.

Notifications (server-pushed events) are used for streaming install
progress: a single ``install.execute`` request triggers many
``install.event`` notifications followed by a final response. The
Tauri client routes the notifications into the SvelteKit UI's
progress widget.
"""

from .server import RpcServer
from .server import run as run

__all__ = ["RpcServer", "run"]
