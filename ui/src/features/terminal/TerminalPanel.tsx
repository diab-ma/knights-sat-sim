import { useEffect, useRef } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";

export default function TerminalPanel() {
  const terminalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = terminalRef.current;
    if (!container) return;

    const terminal = new Terminal({
      allowProposedApi: false,
      linkHandler: null,
      rightClickSelectsWord: false,
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(container);
    fitAddon.fit();

    terminal.writeln("Hello from the terminal panel");
    const socket = new WebSocket("ws://localhost:8000/api/dev/echo");
    socket.binaryType = "arraybuffer";
    let disposed = false;
    let connectionMessageWritten = false;
    const reportDisconnected = () => {
      if (disposed || connectionMessageWritten) return;
      connectionMessageWritten = true;
      terminal.writeln("Not connected to the server");
    };

    socket.onmessage = ({ data }) => {
      if (typeof data === "string") {
        terminal.write(data);
      } else if (data instanceof ArrayBuffer) {
        terminal.write(new Uint8Array(data));
      }
    };
    socket.onerror = reportDisconnected;
    socket.onclose = reportDisconnected;

    const input = terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(data);
    });

    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => fitAddon.fit());
    resizeObserver?.observe(container);
    const fitTerminal = () => fitAddon.fit();
    window.addEventListener("resize", fitTerminal);
    const fitFrame = window.requestAnimationFrame(fitTerminal);

    return () => {
      disposed = true;
      input.dispose();
      resizeObserver?.disconnect();
      window.removeEventListener("resize", fitTerminal);
      window.cancelAnimationFrame(fitFrame);
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socket.close();
      terminal.dispose();
    };
  }, []);

  return (
    <div className="terminal-panel" role="region" aria-label="Terminal">
      <div ref={terminalRef} />
    </div>
  );
}
