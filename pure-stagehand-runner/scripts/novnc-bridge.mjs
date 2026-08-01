#!/usr/bin/env node
import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { WebSocketServer } from "ws";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const listenHost = process.env.NOVNC_LISTEN_HOST || "127.0.0.1";
const listenPort = Number(process.env.NOVNC_PORT || "16092");
const vncHost = process.env.VNC_HOST || "127.0.0.1";
const vncPort = Number(process.env.VNC_PORT || "15992");
const staticRoot = process.env.NOVNC_STATIC_ROOT
  ? path.resolve(process.env.NOVNC_STATIC_ROOT)
  : path.join(root, "vendor", "novnc");

const contentTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".svg", "image/svg+xml"],
  [".ico", "image/x-icon"],
  [".json", "application/json; charset=utf-8"],
  [".wasm", "application/wasm"],
]);

function safeStaticPath(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const rel = decoded === "/" ? "/vnc.html" : decoded;
  const full = path.resolve(staticRoot, "." + rel);
  if (!full.startsWith(staticRoot + path.sep) && full !== staticRoot) {
    return null;
  }
  return full;
}

const server = http.createServer((req, res) => {
  const filePath = safeStaticPath(req.url || "/");
  if (!filePath) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  fs.stat(filePath, (statErr, stat) => {
    if (statErr || !stat.isFile()) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    res.writeHead(200, {
      "content-type":
        contentTypes.get(path.extname(filePath)) || "application/octet-stream",
    });
    fs.createReadStream(filePath).pipe(res);
  });
});

const wss = new WebSocketServer({ noServer: true });

wss.on("connection", (ws) => {
  const socket = net.connect(vncPort, vncHost);

  socket.on("data", (chunk) => {
    if (ws.readyState === ws.OPEN) ws.send(chunk);
  });

  socket.on("error", (error) => {
    if (ws.readyState === ws.OPEN) ws.close(1011, error.message.slice(0, 120));
  });

  socket.on("close", () => {
    if (ws.readyState === ws.OPEN) ws.close();
  });

  ws.on("message", (data) => {
    if (!socket.destroyed) socket.write(Buffer.from(data));
  });

  ws.on("close", () => socket.destroy());
  ws.on("error", () => socket.destroy());
});

server.on("upgrade", (req, socket, head) => {
  const reqPath = (req.url || "").split("?")[0];
  if (reqPath !== "/websockify" && reqPath !== "/websockify/") {
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit("connection", ws, req);
  });
});

server.listen(listenPort, listenHost, () => {
  console.log(
    `noVNC bridge listening on http://${listenHost}:${listenPort} -> ${vncHost}:${vncPort}`,
  );
});
