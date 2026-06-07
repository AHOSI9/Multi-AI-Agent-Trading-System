from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import load_config
from ..orchestrator import MultiAgentTradingSystem


STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Multi-AI Agent Trading System", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_system: MultiAgentTradingSystem | None = None
_runner: asyncio.Task[None] | None = None


DASHBOARD_HTML = """
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Multi-AI Trading System</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111315;
      --panel: #1d2024;
      --panel-2: #252a2f;
      --line: #343b44;
      --text: #eef2f5;
      --muted: #9aa6b2;
      --cyan: #45c9d8;
      --green: #49d17c;
      --amber: #f2b84b;
      --red: #e35f5f;
      --violet: #b66cff;
      --blue: #4f8cff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      min-height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 14px 22px;
      border-bottom: 1px solid var(--line);
      background: #16191d;
    }
    h1, h2, h3 { letter-spacing: 0; }
    h1 { margin: 0; font-size: 20px; font-weight: 650; }
    h2 { margin: 0; font-size: 15px; font-weight: 650; }
    h3 { margin: 0; font-size: 13px; font-weight: 650; }
    main {
      width: min(1440px, calc(100vw - 28px));
      margin: 16px auto 24px;
      display: grid;
      gap: 14px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    button {
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 6px;
      min-height: 34px;
      padding: 0 12px;
      cursor: pointer;
    }
    button.primary { background: var(--green); color: #08140d; border-color: var(--green); font-weight: 700; }
    .status { color: var(--muted); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(6, minmax(140px, 1fr));
      gap: 10px;
    }
    .metric, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .metric { padding: 12px; min-height: 72px; }
    .metric span { color: var(--muted); display: block; font-size: 12px; }
    .metric strong { display: block; font-size: 22px; margin-top: 4px; }
    .metric strong.compact { font-size: 15px; line-height: 1.25; overflow-wrap: anywhere; }
    .ops-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.75fr);
      gap: 14px;
      align-items: stretch;
    }
    .agent-floor {
      position: relative;
      min-height: 560px;
      overflow: hidden;
      background:
        linear-gradient(180deg, rgba(13, 15, 18, 0.08), rgba(13, 15, 18, 0.72)),
        url("/static/agent-office-reference.jpg") center / cover no-repeat;
      border-radius: 8px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
    }
    .agent-floor::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 28% 28%, rgba(255,255,255,0.16), transparent 24%),
        linear-gradient(90deg, rgba(0,0,0,0.08), transparent 40%, rgba(0,0,0,0.18));
      pointer-events: none;
      z-index: 1;
    }
    .floor-head {
      position: absolute;
      z-index: 5;
      left: 16px;
      right: 16px;
      top: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      pointer-events: none;
    }
    .floor-head .status { font-size: 12px; }
    .asset-selector {
      position: absolute;
      z-index: 5;
      left: 16px;
      right: 16px;
      bottom: 14px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 10px;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      background: rgba(16, 19, 23, 0.72);
      backdrop-filter: blur(10px);
    }
    .asset-selector span {
      color: var(--muted);
      font-size: 12px;
      margin-right: 2px;
    }
    .asset-button {
      min-height: 30px;
      border-color: rgba(255,255,255,0.18);
      background: rgba(37, 42, 47, 0.84);
      font-size: 12px;
      padding: 0 10px;
    }
    .asset-button.active {
      background: var(--cyan);
      border-color: var(--cyan);
      color: #041316;
      font-weight: 750;
    }
    .photo-depth {
      position: absolute;
      inset: 0;
      z-index: 2;
      transform: translateZ(0);
    }
    .moving-agent {
      position: absolute;
      width: 34px;
      height: 48px;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%) scale(1.08);
      z-index: 3;
      filter: drop-shadow(0 14px 12px rgba(0,0,0,0.5));
      transition: opacity 0.2s ease;
    }
    .moving-agent.route-trend { animation: routeTrend 24s linear infinite; }
    .moving-agent.route-behavior { animation: routeBehavior 27s linear infinite; }
    .moving-agent.route-sentiment { animation: routeSentiment 25s linear infinite; }
    .moving-agent.route-recorder { animation: routeRecorder 29s linear infinite; }
    .moving-agent.route-tech { animation: routeTech 31s linear infinite; }
    @keyframes routeTrend {
      0%, 100% { left: 17%; top: 46%; }
      25% { left: 30%; top: 34%; }
      50% { left: 39%; top: 43%; }
      75% { left: 27%; top: 56%; }
    }
    @keyframes routeBehavior {
      0%, 100% { left: 44%; top: 54%; }
      25% { left: 54%; top: 44%; }
      50% { left: 61%; top: 55%; }
      75% { left: 48%; top: 66%; }
    }
    @keyframes routeSentiment {
      0%, 100% { left: 70%; top: 39%; }
      25% { left: 80%; top: 50%; }
      50% { left: 72%; top: 61%; }
      75% { left: 62%; top: 48%; }
    }
    @keyframes routeRecorder {
      0%, 100% { left: 24%; top: 72%; }
      25% { left: 36%; top: 68%; }
      50% { left: 43%; top: 76%; }
      75% { left: 32%; top: 82%; }
    }
    @keyframes routeTech {
      0%, 100% { left: 56%; top: 70%; }
      25% { left: 66%; top: 63%; }
      50% { left: 74%; top: 72%; }
      75% { left: 62%; top: 81%; }
    }
    .moving-agent::before {
      content: "";
      position: absolute;
      left: 7px;
      top: 0;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: linear-gradient(145deg, #f4d0ac, #94633f);
      box-shadow: inset -5px -5px 8px rgba(43,22,12,0.28);
    }
    .moving-agent::after {
      content: "";
      position: absolute;
      left: 5px;
      top: 18px;
      width: 24px;
      height: 30px;
      border-radius: 9px 9px 12px 12px;
      background: linear-gradient(160deg, var(--agent-color), rgba(12,13,16,0.82));
      border: 1px solid rgba(255,255,255,0.22);
    }
    .agent-legs {
      position: absolute;
      left: 7px;
      top: 40px;
      width: 20px;
      height: 14px;
    }
    .agent-legs::before,
    .agent-legs::after {
      content: "";
      position: absolute;
      top: 0;
      width: 6px;
      height: 14px;
      border-radius: 4px;
      background: rgba(11, 13, 16, 0.9);
      transform-origin: top center;
      animation: walkLegs 0.8s ease-in-out infinite;
    }
    .agent-legs::before { left: 2px; }
    .agent-legs::after { right: 2px; animation-delay: -0.4s; }
    @keyframes walkLegs {
      0%, 100% { transform: rotate(-13deg); }
      50% { transform: rotate(15deg); }
    }
    .agent-shadow {
      position: absolute;
      left: 50%;
      top: 49px;
      width: 44px;
      height: 12px;
      transform: translateX(-50%);
      border-radius: 50%;
      background: rgba(0,0,0,0.36);
      filter: blur(4px);
    }
    .agent-labels {
      position: absolute;
      inset: 0;
      z-index: 4;
      pointer-events: none;
    }
    .agent-label {
      position: absolute;
      width: min(230px, 42vw);
      left: 50%;
      bottom: calc(100% + 8px);
      transform: translateX(-50%);
      padding: 8px 10px;
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 8px;
      background: rgba(21, 24, 28, 0.76);
      box-shadow: 0 12px 30px rgba(0,0,0,0.24);
      backdrop-filter: blur(8px);
      color: var(--text);
    }
    .agent-label strong { display: block; font-size: 13px; }
    .agent-label span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .side-stack {
      display: grid;
      gap: 14px;
      align-content: start;
    }
    .panel h2 {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .agent-list, .journal-list {
      display: grid;
      gap: 8px;
      padding: 10px;
    }
    .agent-row {
      display: grid;
      grid-template-columns: 12px minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 10px;
      min-height: 68px;
      background: #20242a;
      border: 1px solid #303741;
      border-radius: 8px;
    }
    .agent-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      box-shadow: 0 0 16px currentColor;
    }
    .agent-title { font-weight: 650; overflow-wrap: anywhere; }
    .agent-task {
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .agent-state {
      display: grid;
      justify-items: end;
      gap: 3px;
      min-width: 70px;
      color: var(--muted);
      font-size: 12px;
    }
    .agent-state strong { color: var(--text); font-size: 13px; }
    .data-grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 14px;
    }
    section.panel { overflow: hidden; }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    th { color: var(--muted); font-weight: 600; font-size: 12px; }
    .buy { color: var(--green); font-weight: 650; }
    .sell { color: var(--red); font-weight: 650; }
    .hold { color: var(--muted); font-weight: 650; }
    .journal-item {
      padding: 9px 10px;
      background: #20242a;
      border: 1px solid #303741;
      border-radius: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .journal-item strong { color: var(--text); }
    @media (max-width: 980px) {
      header { align-items: flex-start; flex-direction: column; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .ops-grid, .data-grid { grid-template-columns: 1fr; }
      .agent-floor { min-height: 460px; }
      .asset-selector { position: relative; left: auto; right: auto; bottom: auto; margin: 12px; }
    }
    @media (max-width: 520px) {
      main { width: min(100vw - 16px, 1440px); margin-top: 8px; }
      .metrics { grid-template-columns: 1fr 1fr; }
      .agent-floor { min-height: 420px; }
      .agent-label { width: min(190px, 58vw); }
      .moving-agent { width: 28px; height: 42px; }
      th, td { padding: 8px 7px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Multi-AI Agent Trading System</h1>
    <div class="toolbar">
      <button class="primary" onclick="startSystem()">Start</button>
      <button onclick="stopSystem()">Stop</button>
      <span id="status" class="status">connecting</span>
    </div>
  </header>
  <main>
    <div class="metrics">
      <div class="metric"><span>MT5 ID</span><strong id="mt5-login" class="compact">n/a</strong></div>
      <div class="metric"><span>Broker</span><strong id="mt5-broker" class="compact">n/a</strong></div>
      <div class="metric"><span>Balance</span><strong id="mt5-balance">0.00</strong></div>
      <div class="metric"><span>P/L</span><strong id="mt5-profit">0.00</strong></div>
      <div class="metric"><span>Paper Equity</span><strong id="equity">0.00</strong></div>
      <div class="metric"><span>Running</span><strong id="running">false</strong></div>
    </div>

    <div class="ops-grid">
      <section class="agent-floor">
        <div class="floor-head">
          <h2>Live Trading Office</h2>
          <span id="floor-status" class="status">initializing</span>
        </div>
        <div id="photo-depth" class="photo-depth"></div>
        <div id="agent-labels" class="agent-labels"></div>
        <div class="asset-selector">
          <span>Trading asset</span>
          <div id="asset-buttons" class="toolbar"></div>
        </div>
      </section>

      <div class="side-stack">
        <section class="panel">
          <h2>Agent Workload</h2>
          <div id="agent-list" class="agent-list"></div>
        </section>
        <section class="panel">
          <h2>Record Journal</h2>
          <div id="journal-list" class="journal-list"></div>
        </section>
      </div>
    </div>

    <div class="data-grid">
      <section class="panel">
        <h2>Latest Markets</h2>
        <table>
          <thead><tr><th>Symbol</th><th>Last</th><th>Spread</th><th>Regime</th><th>Signal</th></tr></thead>
          <tbody id="markets"></tbody>
        </table>
      </section>
      <section class="panel">
        <h2>Orders</h2>
        <table>
          <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th></tr></thead>
          <tbody id="orders"></tbody>
        </table>
      </section>
    </div>
  </main>

  <script>
    const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
    const statusEl = document.getElementById("status");
    const floorStatusEl = document.getElementById("floor-status");
    const sideClass = value => value === "buy" ? "buy" : value === "sell" ? "sell" : "hold";
    const agentColors = {
      trend_agent: "#45c9d8",
      trader_behavior_agent: "#f2b84b",
      sentiment_agent: "#b66cff",
      record_keeper_agent: "#49d17c",
      technical_development_agent: "#e35f5f",
    };
    const agentPaths = {
      trend_agent: [[17, 46], [30, 34], [39, 43], [27, 56]],
      trader_behavior_agent: [[44, 54], [54, 44], [61, 55], [48, 66]],
      sentiment_agent: [[70, 39], [80, 50], [72, 61], [62, 48]],
      record_keeper_agent: [[24, 72], [36, 68], [43, 76], [32, 82]],
      technical_development_agent: [[56, 70], [66, 63], [74, 72], [62, 81]],
    };
    const agentNames = {
      trend_agent: "Trend",
      trader_behavior_agent: "Behavior",
      sentiment_agent: "Sentiment",
      record_keeper_agent: "Recorder",
      technical_development_agent: "Tech Dev",
    };
    const routeClasses = {
      trend_agent: "route-trend",
      trader_behavior_agent: "route-behavior",
      sentiment_agent: "route-sentiment",
      record_keeper_agent: "route-recorder",
      technical_development_agent: "route-tech",
    };
    const defaultAgents = [
      "trend_agent",
      "trader_behavior_agent",
      "sentiment_agent",
      "record_keeper_agent",
      "technical_development_agent",
    ].map((agent, index) => ({
      agent,
      role: agentNames[agent],
      status: "waiting",
      current_task: "Waiting for market data",
      direction: "hold",
      confidence: 0,
      workload: 0.2,
      symbol: "",
      index,
    }));

    let latestState = {};
    let activeSymbol = "";
    const assetButtonsEl = document.getElementById("asset-buttons");
    const sceneHandle = createPhotoOfficeScene(document.getElementById("photo-depth"), document.getElementById("agent-labels"));

    async function startSystem() {
      await fetch("/control/start", { method: "POST" });
      await refreshState();
    }
    async function stopSystem() {
      await fetch("/control/stop", { method: "POST" });
      await refreshState();
    }
    window.startSystem = startSystem;
    window.stopSystem = stopSystem;

    async function selectAsset(symbol) {
      const params = new URLSearchParams();
      if (symbol) params.set("symbol", symbol);
      const response = await fetch(`/control/active-symbol?${params.toString()}`, { method: "POST" });
      const result = await response.json().catch(() => ({ active_symbol: symbol || "" }));
      activeSymbol = result.active_symbol || "";
      await refreshState();
    }
    window.selectAsset = selectAsset;

    assetButtonsEl.addEventListener("click", event => {
      const button = event.target.closest(".asset-button");
      if (!button || !assetButtonsEl.contains(button)) return;
      selectAsset(button.dataset.symbol || "");
    });

    async function refreshState() {
      const response = await fetch("/state");
      render(await response.json());
    }

    function normalizeAgents(state) {
      const byId = new Map(defaultAgents.map(agent => [agent.agent, { ...agent }]));
      for (const agent of state.agent_status || []) {
        byId.set(agent.agent, { ...byId.get(agent.agent), ...agent });
      }
      return Array.from(byId.values());
    }

    function render(state) {
      latestState = state;
      document.getElementById("equity").textContent = fmt.format(state.account?.equity || 0);
      document.getElementById("running").textContent = String(state.running);
      const mt5 = state.market_account || {};
      document.getElementById("mt5-login").textContent = mt5.login || "n/a";
      document.getElementById("mt5-broker").textContent = mt5.company || mt5.server || "n/a";
      document.getElementById("mt5-balance").textContent = fmt.format(mt5.balance || 0);
      const profit = Number(mt5.profit || 0);
      const profitEl = document.getElementById("mt5-profit");
      profitEl.textContent = fmt.format(profit);
      profitEl.className = profit > 0 ? "buy" : profit < 0 ? "sell" : "hold";

      const agents = normalizeAgents(state);
      renderAgentList(agents);
      renderJournal(state.agent_journal || []);
      sceneHandle.update(agents, state);
      renderAssetButtons(state);

      const displayTicks = Object.values(state.latest_ticks || {}).filter(tick => !state.active_symbol || tick.symbol === state.active_symbol);
      const markets = displayTicks.map(tick => {
        const behavior = (state.latest_behavior || {})[tick.symbol] || {};
        const signals = (state.latest_signals || {})[tick.symbol] || [];
        const primary = signals.find(s => s.direction !== "hold") || signals[0] || { direction: "hold", confidence: 0 };
        return `<tr>
          <td>${tick.symbol}</td>
          <td>${fmt.format(tick.last)}</td>
          <td>${fmt.format(tick.ask - tick.bid)}</td>
          <td>${behavior.regime || "n/a"}</td>
          <td class="${sideClass(primary.direction)}">${primary.direction} ${fmt.format(primary.confidence)}</td>
        </tr>`;
      }).join("");
      document.getElementById("markets").innerHTML = markets || "<tr><td colspan='5'>No market data</td></tr>";

      const displayOrders = (state.orders || []).filter(order => !state.active_symbol || order.symbol === state.active_symbol);
      const orders = displayOrders.slice(0, 12).map(order => `<tr>
        <td>${String(order.timestamp || "").slice(11, 19)}</td>
        <td>${order.symbol}</td>
        <td class="${sideClass(order.direction)}">${order.direction}</td>
        <td>${fmt.format(order.quantity || 0)}</td>
        <td>${order.status}</td>
      </tr>`).join("");
      document.getElementById("orders").innerHTML = orders || "<tr><td colspan='5'>No orders</td></tr>";
      floorStatusEl.textContent = state.active_symbol ? `live - ${state.active_symbol}` : (state.running ? "live - all assets" : "paused");
    }

    function renderAssetButtons(state) {
      activeSymbol = state.active_symbol || "";
      const symbols = state.symbols || [];
      assetButtonsEl.innerHTML = "";
      const makeButton = (label, symbol) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `asset-button ${activeSymbol === symbol ? "active" : ""}`;
        button.dataset.symbol = symbol;
        button.textContent = label;
        assetButtonsEl.appendChild(button);
      };
      makeButton("All", "");
      for (const symbol of symbols) makeButton(symbol, symbol);
    }

    function renderAgentList(agents) {
      document.getElementById("agent-list").innerHTML = agents.map(agent => {
        const color = agentColors[agent.agent] || "#9aa6b2";
        return `<div class="agent-row">
          <span class="agent-dot" style="color:${color}; background:${color}"></span>
          <div>
            <div class="agent-title">${agentNames[agent.agent] || agent.agent}</div>
            <div class="agent-task">${agent.current_task || agent.rationale || "Monitoring"}</div>
          </div>
          <div class="agent-state">
            <strong class="${sideClass(agent.direction)}">${agent.direction || "hold"}</strong>
            <span>${fmt.format(agent.confidence || 0)}</span>
          </div>
        </div>`;
      }).join("");
    }

    function renderJournal(items) {
      document.getElementById("journal-list").innerHTML = items.slice(0, 8).map(item => `<div class="journal-item">
        <strong>${String(item.timestamp || "").slice(11, 19)}</strong> ${item.symbol || ""} ${item.message || ""}
      </div>`).join("") || `<div class="journal-item">No records yet</div>`;
    }

    function createPhotoOfficeScene(stage, labelRoot) {
      const nodes = new Map();
      for (const agent of defaultAgents) {
        const person = document.createElement("div");
        person.className = `moving-agent ${routeClasses[agent.agent] || ""}`;
        person.style.setProperty("--agent-color", agentColors[agent.agent] || "#9aa6b2");
        person.innerHTML = `<span class="agent-shadow"></span><span class="agent-legs"></span><div class="agent-label"></div>`;
        stage.appendChild(person);
        const label = person.querySelector(".agent-label");
        nodes.set(agent.agent, {
          person,
          label,
          workload: 0.2,
          confidence: 0,
        });
      }

      function update(agents, state) {
        for (const agent of agents) {
          const node = nodes.get(agent.agent);
          if (!node) continue;
          node.workload = Number(agent.workload || 0.2);
          node.confidence = Number(agent.confidence || 0);
          const isFocused = !state.active_symbol || agent.symbol === state.active_symbol || !agent.symbol;
          node.person.style.opacity = isFocused ? "1" : "0.48";
          node.label.style.opacity = isFocused ? "1" : "0.5";
          node.label.innerHTML = `<strong>${agentNames[agent.agent] || agent.agent}</strong>
            <span>${agent.status || "monitoring"} - ${agent.symbol || "system"}</span>
            <span>${agent.current_task || agent.rationale || "Monitoring"}</span>`;
        }
      }
      return { update };
    }

    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/state`);
    ws.onopen = () => statusEl.textContent = "connected";
    ws.onclose = () => statusEl.textContent = "disconnected";
    ws.onmessage = event => render(JSON.parse(event.data));
    refreshState();
  </script>
</body>
</html>
"""


def get_system() -> MultiAgentTradingSystem:
    global _system
    if _system is None:
        config = load_config()
        _system = MultiAgentTradingSystem(config)
    return _system


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/health")
async def health() -> dict[str, Any]:
    system = get_system()
    return {"ok": True, "running": system.running, "execution_mode": system.config.execution_mode}


@app.get("/state")
async def state() -> dict[str, Any]:
    return get_system().snapshot()


@app.get("/storage/{table}")
async def storage(table: str, limit: int = 50) -> list[dict[str, Any]]:
    return get_system().store.latest(table, limit=limit)


@app.post("/control/start")
async def start() -> dict[str, Any]:
    global _runner
    system = get_system()
    if _runner and not _runner.done():
        return {"running": True, "message": "already_running"}
    _runner = asyncio.create_task(system.run_background())
    return {"running": True, "message": "started"}


@app.post("/control/stop")
async def stop() -> dict[str, Any]:
    global _runner
    if _runner and not _runner.done():
        _runner.cancel()
        with suppress(asyncio.CancelledError):
            await _runner
    _runner = None
    get_system().running = False
    return {"running": False, "message": "stopped"}


@app.post("/control/active-symbol")
async def set_active_symbol(symbol: str = "") -> dict[str, Any]:
    system = get_system()
    try:
        active_symbol = system.set_active_symbol(symbol)
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "active_symbol": system.state.active_symbol}
    return {"ok": True, "active_symbol": active_symbol}


@app.post("/control/reset-paper")
async def reset_paper(db_path: str = "runtime/trading_state.sqlite") -> dict[str, Any]:
    global _system, _runner
    if _runner and not _runner.done():
        _runner.cancel()
        with suppress(asyncio.CancelledError):
            await _runner
    config = replace(load_config(), state_db_path=Path(db_path), execution_mode="paper")
    _system = MultiAgentTradingSystem(config)
    _runner = None
    return {"ok": True, "message": "paper_system_reset"}


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_system().snapshot())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
