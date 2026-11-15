"""
scripts/record_demo_video.py — Automated 1080p Browser Video Recorder for MediFlux / NexusChain.

Executes all 10 acts from docs/DEMO_SCRIPT.md against live backend and frontend,
injects Warm Editorial Minimalism chapter cards and visual cursor indicators,
records full 1920x1080 video to docs/demo_video.webm and docs/demo_video.mp4,
and outputs a synchronized docs/VOICEOVER_TIMESTAMPS.md teleprompter guide.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import imageio_ffmpeg
from playwright.async_api import BrowserContext, Page, async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
VIDEOS_DIR = DOCS_DIR / "videos"
WEBM_OUTPUT = DOCS_DIR / "demo_video.webm"
MP4_OUTPUT = DOCS_DIR / "demo_video.mp4"
TIMESTAMPS_DOC = DOCS_DIR / "VOICEOVER_TIMESTAMPS.md"

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"

# Injected CSS & JS for Chapter Progress Banner & Cursor
INJECTED_BANNER_AND_CURSOR = """
(() => {
  if (window.__medifluxInjected) return;
  window.__medifluxInjected = true;

  // Add styles
  const style = document.createElement('style');
  style.id = 'mediflux-recording-styles';
  style.textContent = `
    /* Chapter Progress Pill - Warm Editorial Minimalism */
    #mediflux-demo-banner {
      position: fixed;
      top: 14px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 999999;
      background-color: #031211;
      border: 1.5px solid #00AEBB;
      box-shadow: 0 8px 32px rgba(3, 18, 17, 0.45);
      padding: 7px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
      pointer-events: none;
      font-family: 'Inter', -apple-system, sans-serif;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    #mediflux-demo-badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 800;
      background-color: #00AEBB;
      color: #031211;
      padding: 3px 8px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      shrink-0: 0;
    }
    #mediflux-demo-content {
      display: flex;
      flex-direction: column;
    }
    #mediflux-demo-title {
      font-size: 12.5px;
      font-weight: 700;
      color: #E8E4D3;
      letter-spacing: 0.02em;
      line-height: 1.2;
    }
    #mediflux-demo-subtitle {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      color: #9E988A;
      line-height: 1.2;
      margin-top: 1px;
    }

    /* Virtual Visual Cursor */
    #mediflux-cursor {
      position: fixed;
      top: 0;
      left: 0;
      width: 18px;
      height: 18px;
      margin-top: -9px;
      margin-left: -9px;
      border-radius: 50%;
      background: rgba(0, 174, 187, 0.35);
      border: 2px solid #00AEBB;
      pointer-events: none;
      z-index: 1000000;
      transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
      box-shadow: 0 0 12px rgba(0, 174, 187, 0.7);
    }
    #mediflux-cursor-dot {
      position: absolute;
      top: 50%;
      left: 50%;
      width: 5px;
      height: 5px;
      margin-top: -2.5px;
      margin-left: -2.5px;
      border-radius: 50%;
      background: #FFFFFF;
    }

    /* Click Ripple Animation */
    .mediflux-ripple {
      position: fixed;
      width: 12px;
      height: 12px;
      margin-top: -6px;
      margin-left: -6px;
      border-radius: 50%;
      border: 2px solid #00AEBB;
      pointer-events: none;
      z-index: 999999;
      animation: mediflux-ripple-kf 0.45s ease-out forwards;
    }
    @keyframes mediflux-ripple-kf {
      0% {
        transform: scale(1);
        opacity: 1;
      }
      100% {
        transform: scale(4.8);
        opacity: 0;
      }
    }
  `;
  document.head.appendChild(style);

  // Create banner DOM
  const banner = document.createElement('div');
  banner.id = 'mediflux-demo-banner';
  banner.innerHTML = `
    <div id="mediflux-demo-badge">STEP 01 / 10</div>
    <div id="mediflux-demo-content">
      <div id="mediflux-demo-title">INITIALIZING DEMO</div>
      <div id="mediflux-demo-subtitle">Automated Multi-Agent Supply Chain Walkthrough</div>
    </div>
  `;
  document.body.appendChild(banner);

  // Create cursor DOM
  const cursor = document.createElement('div');
  cursor.id = 'mediflux-cursor';
  cursor.innerHTML = '<div id="mediflux-cursor-dot"></div>';
  cursor.style.transform = 'translate3d(960px, 540px, 0)';
  document.body.appendChild(cursor);

  // Global methods
  window.__setDemoChapter = (step, total, title, subtitle) => {
    const badgeEl = document.getElementById('mediflux-demo-badge');
    const titleEl = document.getElementById('mediflux-demo-title');
    const subEl = document.getElementById('mediflux-demo-subtitle');
    if (badgeEl) badgeEl.textContent = `ACT ${String(step).padStart(2, '0')} / ${String(total).padStart(2, '0')}`;
    if (titleEl) titleEl.textContent = title;
    if (subEl) subEl.textContent = subtitle;
  };

  window.__moveCursor = (x, y) => {
    const cur = document.getElementById('mediflux-cursor');
    if (cur) {
      cur.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    }
  };

  window.__clickRipple = (x, y) => {
    const rip = document.createElement('div');
    rip.className = 'mediflux-ripple';
    rip.style.left = `${x}px`;
    rip.style.top = `${y}px`;
    document.body.appendChild(rip);
    setTimeout(() => rip.remove(), 500);
  };
})();
"""


class DemoRecorder:
    def __init__(self) -> None:
        self.backend_proc: subprocess.Popen[Any] | None = None
        self.frontend_proc: subprocess.Popen[Any] | None = None
        self.start_wall_time = 0.0
        self.act_timestamps: list[dict[str, Any]] = []

    async def ensure_servers(self) -> None:
        """Verify backend and frontend servers are healthy, launching if needed."""
        print("[1/5] Checking backend server (http://127.0.0.1:8000/health)...")
        backend_up = False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{BACKEND_URL}/health")
                if r.status_code == 200:
                    backend_up = True
        except Exception:
            backend_up = False

        if not backend_up:
            print("  -> Spawning FastAPI backend server...")
            py_exe = sys.executable
            self.backend_proc = subprocess.Popen(
                [py_exe, "-m", "uvicorn", "app.main:app", "--port", "8000"],
                cwd=str(ROOT_DIR / "backend"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for backend
            for _ in range(30):
                await asyncio.sleep(1.0)
                try:
                    async with httpx.AsyncClient(timeout=1.0) as client:
                        r = await client.get(f"{BACKEND_URL}/health")
                        if r.status_code == 200:
                            print("  ✓ FastAPI backend is UP!")
                            break
                except Exception:
                    pass

        print("[2/5] Checking frontend server (http://localhost:5173)...")
        frontend_up = False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(FRONTEND_URL)
                if r.status_code == 200:
                    frontend_up = True
        except Exception:
            frontend_up = False

        if not frontend_up:
            print("  -> Spawning Vite frontend server...")
            npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
            self.frontend_proc = subprocess.Popen(
                [npm_cmd, "run", "dev"],
                cwd=str(ROOT_DIR / "frontend"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(30):
                await asyncio.sleep(1.0)
                try:
                    async with httpx.AsyncClient(timeout=1.0) as client:
                        r = await client.get(FRONTEND_URL)
                        if r.status_code == 200:
                            print("  ✓ Vite frontend is UP!")
                            break
                except Exception:
                    pass

        print("[3/5] Resetting MediFlux database state to clean idempotent baseline...")
        reset_res = subprocess.run(
            [sys.executable, "-m", "scripts.reset_demo"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        if reset_res.returncode == 0:
            print("  ✓ Demo baseline state reset complete.")
        else:
            print(f"  ! Warning: reset_demo returned {reset_res.returncode}: {reset_res.stderr}")

    async def inject_helpers(self, page: Page) -> None:
        """Inject the progress banner and cursor styles into current page."""
        try:
            await page.evaluate(INJECTED_BANNER_AND_CURSOR)
        except Exception:
            pass

    async def set_chapter(self, page: Page, step: int, title: str, subtitle: str) -> None:
        """Update on-screen chapter pill."""
        await self.inject_helpers(page)
        await page.evaluate(
            f"window.__setDemoChapter && window.__setDemoChapter({step}, 10, {title!r}, {subtitle!r})"
        )

    async def smart_click(
        self,
        page: Page,
        selector: str,
        pause_before: float = 0.35,
        pause_after: float = 1.0,
    ) -> bool:
        """Animate virtual cursor to element, show ripple ring, and click."""
        try:
            loc = page.locator(selector).first
            await loc.wait_for(state="visible", timeout=6000)
            box = await loc.bounding_box()
            if box:
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                await page.evaluate(f"window.__moveCursor && window.__moveCursor({cx}, {cy})")
                await asyncio.sleep(pause_before)
                await page.evaluate(f"window.__clickRipple && window.__clickRipple({cx}, {cy})")
                await asyncio.sleep(0.15)
                await loc.click(force=True)
                await asyncio.sleep(pause_after)
                return True
        except Exception as e:
            print(f"    ! Selector click fallback for {selector}: {e}")
            try:
                await page.click(selector, timeout=2000, force=True)
                await asyncio.sleep(pause_after)
                return True
            except Exception:
                return False
        return False

    async def smooth_scroll(self, page: Page, delta_y: int, duration_s: float = 0.8) -> None:
        """Smoothly scroll the page vertically."""
        try:
            await page.evaluate(
                f"window.scrollBy({{ top: {delta_y}, left: 0, behavior: 'smooth' }});"
            )
            await asyncio.sleep(duration_s)
        except Exception:
            pass

    async def safe_navigate(
        self,
        page: Page,
        target_path: str,
        link_selector: str | None = None,
        wait_selector: str | None = None,
        pause_after: float = 2.5,
    ) -> None:
        """Navigate smoothly via sidebar link click with direct URL fallback."""
        navigated = False
        if link_selector:
            navigated = await self.smart_click(page, link_selector, pause_after=0.8)
        if not navigated or target_path not in page.url:
            try:
                await page.goto(f"{FRONTEND_URL}{target_path}", wait_until="domcontentloaded")
            except Exception:
                pass
        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=6000)
            except Exception:
                pass
        await asyncio.sleep(pause_after)

    def get_elapsed_str(self) -> str:
        """Return MM:SS since recording start."""
        elapsed = time.perf_counter() - self.start_wall_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        return f"{mins:02d}:{secs:02d}"

    async def run(self) -> None:
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        await self.ensure_servers()

        print("[4/5] Launching Playwright Chromium in 1920x1080 native video mode...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--window-size=1920,1080",
                ],
            )
            context: BrowserContext = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                record_video_dir=str(VIDEOS_DIR),
                record_video_size={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )
            page: Page = await context.new_page()

            # Ensure helpers are injected whenever URL changes
            page.on("load", lambda: asyncio.create_task(self.inject_helpers(page)))

            self.start_wall_time = time.perf_counter()
            print("  ✓ Recording started. Driving all 10 Acts in sequence...\n")

            # =========================================================================
            # ACT 1: Login & Single-Strip Sale 4-Tier Demand Cascade
            # =========================================================================
            act1_start = self.get_elapsed_str()
            print(f"[{act1_start}] Executing Act 1: Login & Single-Strip Sale 4-Tier Cascade...")
            await page.goto(f"{FRONTEND_URL}/login", wait_until="domcontentloaded")
            await page.wait_for_selector('button:has-text("Sign In as ADMIN")', timeout=10000)
            await self.set_chapter(
                page,
                1,
                "ACT 01 / 10 • RETAIL POS DISPENSE & 4-TIER CASCADE",
                "Instantaneous single-strip demand propagation across Pharmacy, Stockist, Distributor & Manufacturer",
            )
            await asyncio.sleep(2.5)

            # Click Sign In as ADMIN
            await self.smart_click(page, 'button:has-text("Sign In as ADMIN")', pause_after=2.0)

            # Lands on /overview
            await page.wait_for_url("**/overview", timeout=10000)
            await self.set_chapter(
                page,
                1,
                "ACT 01 / 10 • NETWORK OVERVIEW & DEMAND INITIATION",
                "25 Topology Nodes across 4 Tiers • Automated Reorder Level Monitoring",
            )
            await asyncio.sleep(3.0)

            # Scroll down to simulator controls
            await self.smooth_scroll(page, 320)
            await asyncio.sleep(1.0)

            # Trigger "Sell 1 Strip"
            await self.smart_click(page, 'button:has-text("Sell 1 Strip")', pause_after=2.5)

            # Navigate to Cascade Replay
            await self.set_chapter(
                page,
                1,
                "ACT 01 / 10 • 4-TIER CASCADE REPLAY GRAPH",
                "Autonomous LangGraph Edge Rescheduling & Commits in under 50ms",
            )
            await self.safe_navigate(page, "/cascade", 'a[href="/cascade"]', wait_selector='.react-flow__node')

            # Wait for nodes to load, click Tier 4
            await asyncio.sleep(2.5)
            await self.smart_click(page, '.react-flow__node:has-text("Tier 4")', pause_after=2.5)
            # Click Tier 1
            await self.smart_click(page, '.react-flow__node:has-text("Tier 1")', pause_after=3.0)

            act1_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 1,
                "title": "Login & Single-Strip Sale 4-Tier Demand Cascade",
                "start": act1_start,
                "end": act1_end,
                "summary": "Authenticates as Network Admin, inspects multi-tier topology KPIs, dispenses 1 strip of Paracetamol 650mg, and visualizes the autonomous 4-tier demand cascade lighting up from retail counter to manufacturer packaging commit.",
            })

            # =========================================================================
            # ACT 2: Demand Burst Spike & Agent Console Telemetry
            # =========================================================================
            act2_start = self.get_elapsed_str()
            print(f"[{act2_start}] Executing Act 2: Demand Burst Spike & Agent Console...")
            await self.safe_navigate(page, "/overview", 'a[href="/overview"]', wait_selector='button:has-text("Burst Spike")')
            await self.set_chapter(
                page,
                2,
                "ACT 02 / 10 • REGIONAL DEMAND BURST & PRODUCTION SCHEDULING",
                "Simulating 10x Retail Surge & Autonomous JIT Batch Rescheduling",
            )
            await self.smooth_scroll(page, 320)
            await self.smart_click(page, 'button:has-text("Burst Spike")', pause_after=2.5)

            # Navigate to Agent Console
            await self.safe_navigate(page, "/agents", 'a[href="/agents"]', wait_selector='table')
            await self.set_chapter(
                page,
                2,
                "ACT 02 / 10 • AGENT CONSOLE & MULTI-AGENT TELEMETRY",
                "Aggregated Token Consumption, Execution Latencies, and LangGraph Traces",
            )
            await asyncio.sleep(3.0)

            # Scroll through breakdown panels
            await self.smooth_scroll(page, 280)
            await asyncio.sleep(2.0)

            # Click top row in Traces Table to open Run Detail Drawer
            await self.smart_click(page, "table tbody tr:first-child", pause_after=3.0)
            # Close drawer
            await self.smart_click(page, ".fixed.inset-0 button:has(svg)", pause_after=1.5)

            act2_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 2,
                "title": "Demand Burst, JIT Production & Agent Console",
                "start": act2_start,
                "end": act2_end,
                "summary": "Simulates a regional demand burst spike, inspects multi-agent execution telemetry across 18 specialized LangGraph agents, verifies token consumption metrics, and audits deep run diagnostics in the drawer.",
            })

            # =========================================================================
            # ACT 3: Human-in-the-Loop (HITL) Approvals Inbox
            # =========================================================================
            act3_start = self.get_elapsed_str()
            print(f"[{act3_start}] Executing Act 3: HITL Approvals Inbox...")
            await self.safe_navigate(page, "/approvals", 'a[href="/approvals"]', wait_selector='.cursor-pointer')
            await self.set_chapter(
                page,
                3,
                "ACT 03 / 10 • HUMAN-IN-THE-LOOP (HITL) APPROVALS INBOX",
                "Supervisory Decision Gate for High-Risk Statutory Operations & Code Mutators",
            )
            await asyncio.sleep(2.5)

            # Select pending task
            await self.smart_click(page, ".cursor-pointer:first-child", pause_after=2.0)
            await self.smooth_scroll(page, 200)

            # Type decision note
            try:
                txt = page.locator('textarea[placeholder*="operational reasoning"]').first
                if await txt.count() > 0:
                    await txt.fill("Verified during live demo walkthrough; approved for execution.")
                    await asyncio.sleep(1.0)
            except Exception:
                pass

            # Click Approve & Resume Graph
            await self.smart_click(page, 'button:has-text("Approve & Resume Graph")', pause_after=3.5)

            act3_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 3,
                "title": "Human-in-the-Loop (HITL) Approvals Inbox",
                "start": act3_start,
                "end": act3_end,
                "summary": "Reviews an autonomous checkpoint paused by supervisor policy, inspects agent trigger reasoning and code diff context, logs operator justification, and executes one-click resumption of the paused workflow.",
            })

            # =========================================================================
            # ACT 4: Cold-Chain Telemetry & Autonomous Batch Quarantine
            # =========================================================================
            act4_start = self.get_elapsed_str()
            print(f"[{act4_start}] Executing Act 4: Cold-Chain IoT Telemetry & Auto-Quarantine...")
            await self.safe_navigate(page, "/cold-chain", 'a[href="/cold-chain"]', wait_selector='button:has-text("Trigger Thermal Excursion")')
            await self.set_chapter(
                page,
                4,
                "ACT 04 / 10 • COLD-CHAIN IOT & ARRHENIUS AUTO-QUARANTINE",
                "2.0°C – 8.0°C Biologic Envelope Monitoring & Kinetic Degradation Modeling",
            )
            await asyncio.sleep(3.0)

            # Trigger Thermal Excursion
            await self.smart_click(page, 'button:has-text("Trigger Thermal Excursion")', pause_after=3.5)

            # Scroll down to see excursion analyst diagnosis and restock link
            await self.smooth_scroll(page, 350)
            await asyncio.sleep(3.5)

            act4_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 4,
                "title": "Cold-Chain Telemetry & Autonomous Batch Quarantine",
                "start": act4_start,
                "end": act4_end,
                "summary": "Monitors temperature-sensitive biologics in transit, injects a 14.2°C thermal spike, demonstrates real-time Arrhenius kinetic potency degradation, autonomous network-wide quarantine action, and dynamic replenishment routing.",
            })

            # =========================================================================
            # ACT 5: Sovereign Multimodal Prescription Scanner
            # =========================================================================
            act5_start = self.get_elapsed_str()
            print(f"[{act5_start}] Executing Act 5: Sovereign Prescription Scanner...")
            await self.safe_navigate(page, "/prescriptions", 'a[href="/prescriptions"]', wait_selector='button:has-text("Scan & Validate Prescription")')
            await self.set_chapter(
                page,
                5,
                "ACT 05 / 10 • SOVEREIGN PRESCRIPTION SCANNER (DPDP COMPLIANT)",
                "Local CDSCO Compliance OCR, Irreversible PII Redaction, and MCI Registry Validation",
            )
            await asyncio.sleep(2.5)

            # Select Schedule H Valid fixture
            await self.smart_click(page, 'button:has-text("Schedule H Valid")', pause_after=2.0)
            # Scan & Validate
            await self.smart_click(page, 'button:has-text("Scan & Validate Prescription")', pause_after=3.5)

            # Scroll down to see approved verdict
            await self.smooth_scroll(page, 200)
            await asyncio.sleep(2.5)

            # Select Unverified Doctor fixture
            await self.smart_click(page, 'button:has-text("Unverified Doctor")', pause_after=2.0)
            await self.smart_click(page, 'button:has-text("Scan & Validate Prescription")', pause_after=3.5)

            act5_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 5,
                "title": "Sovereign Prescription Scanner & Schedule H Compliance",
                "start": act5_start,
                "end": act5_end,
                "summary": "Validates doctor prescriptions on-premises with zero cloud data leakage, verifies physician registration against the statutory council registry, enforces DPDP Act 2023 patient privacy redactions, and refuses to dispense on unlisted credentials.",
            })

            # =========================================================================
            # ACT 6: Self-Evolving Adapter Forge
            # =========================================================================
            act6_start = self.get_elapsed_str()
            print(f"[{act6_start}] Executing Act 6: Self-Evolving Adapter Forge...")
            await self.safe_navigate(page, "/adapter-forge", 'a[href="/adapter-forge"]', wait_selector='button:has-text("Forge & Register Adapter")')
            await self.set_chapter(
                page,
                6,
                "ACT 06 / 10 • SELF-EVOLVING ADAPTER FORGE",
                "Zero-Code Dynamic Ingestion of Proprietary ERP Formats via Guarded Python AST",
            )
            await asyncio.sleep(2.5)

            # Select preset
            await self.smart_click(page, 'button:has-text("CSV: Legacy")', pause_after=1.5)
            # Forge & Register Adapter
            await self.smart_click(page, 'button:has-text("Forge & Register Adapter")', pause_after=4.0)

            # Scroll through generated Python code & Try It Live box
            await self.smooth_scroll(page, 450)
            await asyncio.sleep(2.5)

            # Click Ingest Raw Payload
            await self.smart_click(page, 'button:has-text("Ingest Raw Payload")', pause_after=3.5)

            act6_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 6,
                "title": "Self-Evolving Adapter Forge (Zero-Code ERP Ingestion)",
                "start": act6_start,
                "end": act6_end,
                "summary": "Synthesizes Python transformation logic on the fly for unstandardized legacy pharmacy billing CSVs, executes AST security sandbox verification (0 OS imports, 0 network calls), registers the module, and verifies live canonical ingestion.",
            })

            # =========================================================================
            # ACT 7: Regulatory Hot-Swap Lab
            # =========================================================================
            act7_start = self.get_elapsed_str()
            print(f"[{act7_start}] Executing Act 7: Regulatory Hot-Swap Lab...")
            await self.safe_navigate(page, "/regulatory-lab", 'a[href="/regulatory-lab"]', wait_selector='button:has-text("Run Regulatory Pipeline")')
            await self.set_chapter(
                page,
                7,
                "ACT 07 / 10 • REGULATORY HOT-SWAP LAB & POLICY ENGINE",
                "Zero-Downtime DPCO Price Ceiling Patching and Immediate Rollback Engine",
            )
            await asyncio.sleep(2.0)

            # Scroll down to test live rule engine before hot-swap
            await self.smooth_scroll(page, 400)
            await self.smart_click(page, 'button:has-text("Test Live Rule Engine")', pause_after=2.5)

            # Scroll up to run pipeline
            await self.smooth_scroll(page, -400)
            await self.smart_click(page, 'button:has-text("Run Regulatory Pipeline")', pause_after=4.0)

            # Approve Gate & Hot-Swap Now
            await self.smart_click(page, 'button:has-text("Approve Gate & Hot-Swap Now")', pause_after=3.5)

            # Scroll down to show price capped at 12.50
            await self.smooth_scroll(page, 400)
            await asyncio.sleep(3.0)

            act7_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 7,
                "title": "Regulatory Hot-Swap Lab (Zero-Downtime Code Mutation)",
                "start": act7_start,
                "end": act7_end,
                "summary": "Parses NPPA gazette notifications, generates verified DPCO pricing engine patches, stages side-by-side AST diffs, executes an atomic in-process hot-swap without restarting the server, and proves immediate statutory ceiling enforcement.",
            })

            # =========================================================================
            # ACT 8: Cryptographic Tamper-Evident Audit Ledger
            # =========================================================================
            act8_start = self.get_elapsed_str()
            print(f"[{act8_start}] Executing Act 8: Cryptographic Audit Ledger...")
            await self.safe_navigate(page, "/audit", 'a[href="/audit"]', wait_selector='button:has-text("Verify Hash Chain Integrity")')
            await self.set_chapter(
                page,
                8,
                "ACT 08 / 10 • CRYPTOGRAPHIC TAMPER-EVIDENT AUDIT LEDGER",
                "SHA-256 Rolling Hash Chain Verifying Zero State Corruption Across Sequential Mutations",
            )
            await asyncio.sleep(2.5)

            # Verify Hash Chain Integrity
            await self.smart_click(page, 'button:has-text("Verify Hash Chain Integrity")', pause_after=3.5)

            # Click top audit row to inspect prev_hash -> entry_hash
            await self.smart_click(page, "table tbody tr:first-child", pause_after=3.5)

            act8_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 8,
                "title": "Cryptographic Tamper-Evident Audit Ledger",
                "start": act8_start,
                "end": act8_end,
                "summary": "Traverses the cryptographic ledger, validates sequential SHA-256 parent-child hashes, inspects the immutable audit inspector drawer, and proves that supply chain state records are mathematically tamper-evident.",
            })

            # =========================================================================
            # ACT 9: Network Copilot & Developer Portal
            # =========================================================================
            act9_start = self.get_elapsed_str()
            print(f"[{act9_start}] Executing Act 9: Copilot & Developer Portal...")
            await self.safe_navigate(page, "/copilot", 'a[href="/copilot"]', wait_selector='button:has-text("Which pharmacies")')
            await self.set_chapter(
                page,
                9,
                "ACT 09 / 10 • NETWORK COPILOT & SEMANTIC GROUNDING",
                "Natural Language Supply Chain Inquiries with Verified pgvector Citations",
            )
            await asyncio.sleep(2.0)

            # Click suggested question
            await self.smart_click(
                page,
                'button:has-text("Which pharmacies are at risk of running out of Paracetamol 500mg?")',
                pause_after=4.5,
            )

            # Navigate to Developer Portal
            await self.safe_navigate(page, "/developer", 'a[href="/developer"]', wait_selector='button:has-text("1. Scoped API Keys")')
            await self.set_chapter(
                page,
                9,
                "ACT 09 / 10 • DEVELOPER PORTAL (API KEYS, WEBHOOKS, MCP)",
                "Cryptographic API Provisioning, HMAC-SHA256 Webhooks, and Official MCP Tool Registry",
            )
            await asyncio.sleep(2.5)

            # Fill Key Name and generate key
            try:
                inp = page.locator('input[placeholder*="Apollo Pharmacy"]').first
                if await inp.count() > 0:
                    await inp.fill("Partner-ERP-Sync")
                    await asyncio.sleep(1.0)
            except Exception:
                pass
            await self.smart_click(page, 'button:has-text("Provision New Developer Key")', pause_after=3.0)

            # Switch tabs: Webhooks, Snippets, MCP
            await self.smart_click(page, 'button:has-text("2. Webhooks & Deliveries")', pause_after=2.5)
            await self.smart_click(page, 'button:has-text("3. Code Snippets & OpenAPI")', pause_after=2.5)
            await self.smart_click(page, 'button:has-text("4. MCP Server Hub")', pause_after=3.0)

            act9_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 9,
                "title": "RLS-Scoped Network Copilot & Developer Portal",
                "start": act9_start,
                "end": act9_end,
                "summary": "Executes natural language operational inquiries grounded in pgvector embeddings with clickable citations, provisions scoped 256-bit API keys, audits HMAC-SHA256 delivery logs, and explores registered Model Context Protocol (MCP) tools.",
            })

            # =========================================================================
            # ACT 10: Desktop Packaging & Role-Based Isolation Closing
            # =========================================================================
            act10_start = self.get_elapsed_str()
            print(f"[{act10_start}] Executing Act 10: Desktop Packaging & RBAC Isolation...")
            await self.set_chapter(
                page,
                10,
                "ACT 10 / 10 • DESKTOP RUNTIME & MULTI-TENANT ISOLATION",
                "Native Tauri Shell Bridge, Hardware Notifications, and Dynamic Role Restriction",
            )

            # Open Backend Settings modal
            await self.smart_click(page, 'button:has-text("Backend")', pause_after=2.0)
            await asyncio.sleep(1.5)

            # Test Ping
            await self.smart_click(page, 'button:has-text("Test Ping")', pause_after=2.0)

            # Test Alert Notification
            await self.smart_click(page, 'button:has-text("Test Approval Alert")', pause_after=2.0)

            # Close Modal
            await self.smart_click(page, 'button:has-text("Cancel")', pause_after=2.0)

            # Click Switch Role in sidebar
            await self.safe_navigate(page, "/login", 'a:has-text("Switch Role")', wait_selector='button:has-text("Sign In as PHARMACY")')

            # Sign in as Pharmacy
            await self.set_chapter(
                page,
                10,
                "ACT 10 / 10 • ROLE-BASED SCOPE RESTRICTION (RETAIL PHARMACY)",
                "Row-Level Security Restricts Navigation and Data Scope Exclusively to Local Node",
            )
            await self.smart_click(page, 'button:has-text("Sign In as PHARMACY")', pause_after=3.5)
            await page.wait_for_url("**/overview", timeout=8000)
            await asyncio.sleep(4.0)

            act10_end = self.get_elapsed_str()
            self.act_timestamps.append({
                "act": 10,
                "title": "Desktop Packaging & Role-Based Isolation Closing",
                "start": act10_start,
                "end": act10_end,
                "summary": "Demonstrates native desktop bridge capabilities including hardware latency probes and push notifications, followed by switching to a retail pharmacy persona to verify instant multi-tenant RLS UI and data filtering.",
            })

            # Complete recording
            print(f"[{act10_end}] Walkthrough execution complete! Flushing video buffers...")
            await page.close()
            await context.close()
            await browser.close()

        # Find recorded webm file
        webm_files = sorted(VIDEOS_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not webm_files:
            raise RuntimeError("No recorded .webm video was generated by Playwright!")

        recorded_webm = webm_files[0]
        shutil.copy(recorded_webm, WEBM_OUTPUT)
        webm_size_mb = WEBM_OUTPUT.stat().st_size / (1024 * 1024)
        print(f"  ✓ Saved {WEBM_OUTPUT} ({webm_size_mb:.2f} MB)")

        # Convert to MP4 using imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"[5/5] Converting {WEBM_OUTPUT.name} to {MP4_OUTPUT.name} via FFmpeg...")
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(WEBM_OUTPUT),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "20",
            "-preset",
            "medium",
            str(MP4_OUTPUT),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and MP4_OUTPUT.exists():
            mp4_size_mb = MP4_OUTPUT.stat().st_size / (1024 * 1024)
            print(f"  ✓ Saved {MP4_OUTPUT} ({mp4_size_mb:.2f} MB)")
        else:
            print(f"  ! FFmpeg conversion notice: {res.stderr[:200]}")

        # Write Synced Voiceover Teleprompter Guide
        self.generate_voiceover_script()

        # Clean up spawned processes if any
        if self.backend_proc:
            self.backend_proc.terminate()
        if self.frontend_proc:
            self.frontend_proc.terminate()

    def generate_voiceover_script(self) -> None:
        """Generate docs/VOICEOVER_TIMESTAMPS.md with exact recorded timestamps."""
        total_duration = self.act_timestamps[-1]["end"] if self.act_timestamps else "03:45"
        webm_size = WEBM_OUTPUT.stat().st_size / (1024 * 1024) if WEBM_OUTPUT.exists() else 0.0
        mp4_size = MP4_OUTPUT.stat().st_size / (1024 * 1024) if MP4_OUTPUT.exists() else 0.0

        content = f"""# MediFlux / NexusChain — Synchronized Demo Video & Voiceover Teleprompter

> **Video Title**: MediFlux (NexusChain) — 10-Step Autonomous Supply Chain Walkthrough
> **Total Duration**: `{total_duration}` (Measured Elapsed Run)
> **Master Resolution**: `1920 × 1080 Full HD (1080p60)`
> **Artifacts Produced**:
> - WebM Source: [`docs/demo_video.webm`](file:///{WEBM_OUTPUT.as_posix()}) (`{webm_size:.2f} MB`)
> - MP4 Universal: [`docs/demo_video.mp4`](file:///{MP4_OUTPUT.as_posix()}) (`{mp4_size:.2f} MB`)

---

## 1. Master Timing Summary Table

| Act | Scene / Feature Focus | Measured Window | Duration |
| :--- | :--- | :---: | :---: |
"""
        for item in self.act_timestamps:
            act_num = item["act"]
            title = item["title"]
            w = f"`{item['start']} – {item['end']}`"
            # Calculate duration seconds
            s_m, s_s = map(int, item["start"].split(":"))
            e_m, e_s = map(int, item["end"].split(":"))
            dur_s = (e_m * 60 + e_s) - (s_m * 60 + s_s)
            content += f"| **Act {act_num}** | {title} | {w} | {dur_s}s |\n"

        content += """
---

## 2. Word-for-Word Voiceover Teleprompter Script

"""
        voiceover_narrations = {
            1: (
                "Welcome to MediFlux — an AI-native autonomous pharmaceutical supply chain network. "
                "Today we are demonstrating the core promise of the platform: instantaneous single-unit retail demand propagation. "
                "We begin at the Supply Chain Access Portal and sign in with the Network Admin persona. "
                "On our central Overview dashboard, 25 topological nodes across India are monitored in real time. "
                "Notice how our inventory rows track reorder points dynamically. "
                "Now, watch closely: we click 'Sell 1 Strip' of Paracetamol 650mg at a retail pharmacy counter. "
                "Instantly, an autonomous LangGraph agent cascade propagates up the entire supply chain. "
                "In our Demand Cascade graph, Tier 4 Pharmacy detects the stockout, Tier 3 Stockist reserves regional safety stock, "
                "Tier 2 Distributor re-optimizes delivery routes, and Tier 1 Manufacturer automatically reschedules the packaging line — all completed in under 50 milliseconds."
            ),
            2: (
                "Next, we simulate real-world regional volatility. "
                "From our simulator control panel, we trigger a 'Burst Spike' representing a sudden seasonal dengue surge. "
                "Switching over to the AI Agent Console, we observe live telemetry across all 18 production LangGraph agents. "
                "The KPI cards aggregate real-time execution counts, millisecond latencies, and token budgets. "
                "Notice how token consumption across our 4-tier demand cascade is strictly metered at approximately 1,350 tokens per event. "
                "Opening the Run Detail Drawer reveals the full structured JSON payload and model routing decisions."
            ),
            3: (
                "Autonomous systems require rigorous supervisory governance. "
                "This brings us to the Human-in-the-Loop Approvals Inbox. "
                "Whenever an agent encounters high-risk statutory operations — such as a price ceiling modification or cold-chain anomaly — it pauses execution at a LangGraph checkpoint. "
                "Here, we inspect the agent's trigger diagnosis, review the staged code diff, and provide our operational justification. "
                "With one click on 'Approve & Resume Graph', the workflow resumes deterministically without manual system intervention."
            ),
            4: (
                "Now let's examine cold-chain telemetry for temperature-sensitive biologics such as insulin and vaccines. "
                "On the Cold Chain Monitor, active batches report live IoT environmental sensor readings strictly within the 2.0°C to 8.0°C envelope. "
                "We simulate a transit breach by clicking 'Trigger Thermal Excursion'. "
                "Watch the temperature curve spike to 14.2°C: our Arrhenius kinetic degradation model immediately calculates shelf-life decay, "
                "flips the batch status to QUARANTINED, zeroes available inventory to prevent hazardous retail dispensing, "
                "and triggers the Dynamic Balancing Agent to route replacement stock from the nearest depot."
            ),
            5: (
                "Prescription compliance is enforced by our Sovereign Multimodal Scanner. "
                "Notice the 'Sensitivity: Sensitive • Local Sovereign Execution' badge. Under the Digital Personal Data Protection Act of 2023, "
                "patient identities are irreversibly redacted to initials on-premises before any data persists. "
                "We test a valid Schedule H prescription: our sovereign parser verifies the physician against the statutory Medical Council registry and grants an 'Approve Dispense' verdict. "
                "When presented with an unverified doctor fixture, the system strictly refuses to guess, flagging the prescription for pharmacist review."
            ),
            6: (
                "India has over 800,000 independent pharmacies running proprietary billing systems. "
                "The Self-Evolving Adapter Forge eliminates manual integration glue code. "
                "We feed the forge an unstandardized legacy pharmacy CSV. "
                "Our multi-agent pipeline inspects the schema, synthesizes Python transformation logic, and runs it through an AST security guard to verify zero banned system imports. "
                "In the live sandbox, we ingest the legacy payload and observe it instantly transformed into a normalized canonical SaleEvent ready for event bus propagation."
            ),
            7: (
                "Next is the Regulatory Hot-Swap Lab, enabling zero-downtime policy enforcement. "
                "Currently, our live rule engine accepts Paracetamol at ₹25.00 uncapped. "
                "When the National Pharmaceutical Pricing Authority issues a DPCO gazette ceiling, our pipeline extracts the ₹12.50 mandate, "
                "generates pricing_engine v2, and stages a side-by-side diff. "
                "Upon compliance approval, v2 is hot-swapped in-process without restarting the backend. "
                "Re-testing immediately shows the price capped at ₹12.50, with one-click rollback ready if needed."
            ),
            8: (
                "Every state transition in MediFlux is cryptographically sealed in our Audit Ledger. "
                "Clicking 'Verify Hash Chain Integrity' performs a full mathematical traversal of our SHA-256 rolling chain, "
                "confirming that the ledger is 100% intact from Genesis to Head. "
                "Selecting any record displays the parent hash and entry digest, proving that historical inventory movements and pricing modifications are tamper-evident."
            ),
            9: (
                "For operational visibility, Network Copilot provides grounded natural language question-answering. "
                "We ask: 'Which pharmacies are at risk of running out of Paracetamol 500mg?'. "
                "The agent synthesizes live inventory state via pgvector semantic embeddings, citing exact facilities with clickable reference chips. "
                "Moving to the Developer Portal, engineering teams can provision cryptographically random 256-bit API keys, "
                "monitor HMAC-SHA256 webhook deliveries, and explore official Model Context Protocol tools for AI IDE integration."
            ),
            10: (
                "Finally, we highlight MediFlux's desktop capabilities and multi-tenant security boundaries. "
                "Opening the Runtime Settings modal, we verify live backend ping latency and test native desktop push notifications for urgent checkpoints. "
                "To demonstrate multi-tenant Row-Level Security, we switch our user persona to a Retail Pharmacy. "
                "Instantly, the entire sidebar and data scope restrict exclusively to the local pharmacy node. "
                "This concludes the MediFlux walkthrough — an autonomous, sovereign, and hyper-connected pharmaceutical supply chain for India."
            ),
        }

        for item in self.act_timestamps:
            act_num = item["act"]
            title = item["title"]
            w = f"`{item['start']} – {item['end']}`"
            narr = voiceover_narrations.get(act_num, "")
            content += f"""### Act {act_num}: {title} ({w})

**Visual Cues on Screen:**
- *{item['summary']}*

**Voiceover Script:**
> "{narr}"

---
"""
        TIMESTAMPS_DOC.write_text(content, encoding="utf-8")
        print(f"  ✓ Saved synchronized teleprompter to {TIMESTAMPS_DOC}")


async def main() -> None:
    recorder = DemoRecorder()
    await recorder.run()


if __name__ == "__main__":
    asyncio.run(main())
