// JSON-RPC 2.0 client over stdio — talks to the Python installer
// subprocess. Built around `tokio::process::Child` so the read loop
// doesn't block Tauri's main loop.

use std::process::{Command as StdCommand, Stdio};
use std::sync::atomic::{AtomicI64, Ordering};

use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

pub struct RpcClient {
    child: Child,
    next_id: AtomicI64,
    // Stdout reader is held inside an async lock so call() can read
    // line-by-line without spawning a long-lived background task.
    stdout: Mutex<BufReader<tokio::process::ChildStdout>>,
}

impl RpcClient {
    /// Find a Python interpreter and spawn `python -m
    /// recordorai_installer --rpc`. Tries `python3` first, then
    /// `python`. Returns an error if neither works.
    pub fn spawn_python() -> Result<Self, String> {
        let candidates = ["python3", "python"];
        for bin in candidates {
            // Smoke-test the candidate synchronously before committing.
            let probe = StdCommand::new(bin)
                .arg("-c")
                .arg("import recordorai_installer")
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            match probe {
                Ok(s) if s.success() => {
                    let mut cmd = Command::new(bin);
                    cmd.arg("-m")
                        .arg("recordorai_installer")
                        .arg("--rpc")
                        .stdin(Stdio::piped())
                        .stdout(Stdio::piped())
                        .stderr(Stdio::piped());
                    let mut child = cmd
                        .spawn()
                        .map_err(|e| format!("spawn({}): {}", bin, e))?;
                    let stdout = child
                        .stdout
                        .take()
                        .ok_or_else(|| "child has no stdout".to_string())?;
                    return Ok(Self {
                        child,
                        next_id: AtomicI64::new(1),
                        stdout: Mutex::new(BufReader::new(stdout)),
                    });
                }
                _ => continue,
            }
        }
        Err(format!(
            "Could not find a Python with `recordorai_installer` installed. \
             Tried: {:?}",
            candidates
        ))
    }

    /// Issue one JSON-RPC request and return the result, treating any
    /// notifications received in the meantime as transient (consumed
    /// and discarded).
    pub async fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        self.call_streaming(method, params, |_n| {}).await
    }

    /// Issue one JSON-RPC request; invoke `on_notification` for every
    /// `install.event`-style notification that arrives before the
    /// final response. Returns the result value.
    pub async fn call_streaming<F>(
        &mut self,
        method: &str,
        params: Value,
        mut on_notification: F,
    ) -> Result<Value, String>
    where
        F: FnMut(&Value),
    {
        let req_id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let request = json!({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        });
        let line = format!("{}\n", request);

        let stdin = self
            .child
            .stdin
            .as_mut()
            .ok_or_else(|| "child stdin closed".to_string())?;
        stdin
            .write_all(line.as_bytes())
            .await
            .map_err(|e| format!("rpc write: {}", e))?;
        stdin.flush().await.map_err(|e| format!("rpc flush: {}", e))?;

        // Read responses until we see the matching id.
        let mut stdout = self.stdout.lock().await;
        let mut buf = String::new();
        loop {
            buf.clear();
            let n = stdout
                .read_line(&mut buf)
                .await
                .map_err(|e| format!("rpc read: {}", e))?;
            if n == 0 {
                return Err("rpc child closed stdout".into());
            }
            let msg: Value = serde_json::from_str(buf.trim())
                .map_err(|e| format!("rpc parse: {} (line: {:?})", e, buf))?;

            // Notification — pass to handler and keep reading.
            if msg.get("id").is_none() && msg.get("method").is_some() {
                on_notification(&msg);
                continue;
            }

            // Response — match on id.
            if let Some(id) = msg.get("id").and_then(Value::as_i64) {
                if id != req_id {
                    // Out-of-order response — surface as error.
                    return Err(format!(
                        "rpc id mismatch: expected {}, got {}",
                        req_id, id
                    ));
                }
                if let Some(err) = msg.get("error") {
                    return Err(format!("rpc error: {}", err));
                }
                return Ok(msg.get("result").cloned().unwrap_or(Value::Null));
            }

            return Err(format!("rpc malformed message: {:?}", buf));
        }
    }
}

impl Drop for RpcClient {
    fn drop(&mut self) {
        // Best-effort cleanup on shutdown.
        let _ = self.child.start_kill();
    }
}
