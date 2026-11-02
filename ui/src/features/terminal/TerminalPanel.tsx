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
    terminal.write("$ ");

    let currentLineLength = 0;
    const input = terminal.onData((data) => {
      if (data === "\r" || data === "\n") {
        terminal.write("\r\n$ ");
        currentLineLength = 0;
      } else if (data === "\u007f" || data === "\b") {
        if (currentLineLength > 0) {
          terminal.write("\b \b");
          currentLineLength -= 1;
        }
      } else if (data === "\u0003") {
        terminal.write("^C\r\n$ ");
        currentLineLength = 0;
      } else {
        terminal.write(data);
        currentLineLength += [...data].length;
      }
    });

    const preventClipboardAccess = (event: ClipboardEvent) => {
      event.preventDefault();
    };
    container.addEventListener("copy", preventClipboardAccess, true);
    container.addEventListener("cut", preventClipboardAccess, true);
    container.addEventListener("paste", preventClipboardAccess, true);

    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => fitAddon.fit());
    resizeObserver?.observe(container);
    const fitTerminal = () => fitAddon.fit();
    window.addEventListener("resize", fitTerminal);
    const fitFrame = window.requestAnimationFrame(fitTerminal);

    return () => {
      input.dispose();
      resizeObserver?.disconnect();
      window.removeEventListener("resize", fitTerminal);
      window.cancelAnimationFrame(fitFrame);
      container.removeEventListener("copy", preventClipboardAccess, true);
      container.removeEventListener("cut", preventClipboardAccess, true);
      container.removeEventListener("paste", preventClipboardAccess, true);
      terminal.dispose();
    };
  }, []);

  return (
    <div className="terminal-panel" role="region" aria-label="Terminal">
      <div ref={terminalRef} />
    </div>
  );
}
