"""Automated Viewport and Zero-Scroll Verification Tests using Headless Edge CDP.

Tests Section 15.6 Viewport Requirements:
- 1366 × 768 Desktop (Zero Scroll: scrollHeight <= innerHeight and scrollWidth <= innerWidth)
- 1440 × 900 Desktop (Zero Scroll)
- 1920 × 1080 Desktop (Zero Scroll)
- 390 × 844 Mobile (Responsive Stack, No Horizontal Overflow: scrollWidth <= innerWidth)
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.request
import pytest
import websockets


EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


@pytest.mark.skipif(not os.path.exists(EDGE_PATH), reason="Microsoft Edge binary not found")
def test_all_viewports_and_zero_scroll():
    async def run_checks():
        port = 9225
        proc = subprocess.Popen([
            EDGE_PATH,
            "--headless=new",
            f"--remote-debugging-port={port}",
            "--disable-gpu",
            "--no-sandbox",
            "http://127.0.0.1:5000/",
        ])
        await asyncio.sleep(2)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json") as resp:
                targets = json.loads(resp.read().decode("utf-8"))
                page = next(t for t in targets if t.get("type") == "page")
                ws_url = page["webSocketDebuggerUrl"]

            async with websockets.connect(ws_url) as ws:
                msg_id = 1

                async def send(method, params=None):
                    nonlocal msg_id
                    cid = msg_id
                    msg_id += 1
                    await ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
                    while True:
                        res = json.loads(await ws.recv())
                        if res.get("id") == cid:
                            return res.get("result", {})

                # Navigate
                await send("Page.navigate", {"url": "http://127.0.0.1:5000/"})
                await asyncio.sleep(1)

                viewports = [
                    (1366, 768, True),
                    (1440, 900, True),
                    (1920, 1080, True),
                    (390, 844, False),
                ]

                for w, h, is_desktop in viewports:
                    await send("Emulation.setDeviceMetricsOverride", {
                        "width": w,
                        "height": h,
                        "deviceScaleFactor": 1,
                        "mobile": not is_desktop,
                    })
                    await asyncio.sleep(0.4)

                    for tab_name, tab_sel in [("Overview", "#tab-overview"), ("Recommendations", "#tab-recommendations")]:
                        await send("Runtime.evaluate", {
                            "expression": f'document.querySelector("{tab_sel}").click()'
                        })
                        await asyncio.sleep(0.3)

                        eval_res = await send("Runtime.evaluate", {
                            "expression": """({
                                scrollHeight: document.documentElement.scrollHeight,
                                clientHeight: window.innerHeight,
                                scrollWidth: document.documentElement.scrollWidth,
                                clientWidth: window.innerWidth,
                            })""",
                            "returnByValue": True,
                        })
                        val = eval_res.get("result", {}).get("value", {})
                        sH = val.get("scrollHeight")
                        cH = val.get("clientHeight")
                        sW = val.get("scrollWidth")
                        cW = val.get("clientWidth")

                        if is_desktop:
                            assert sH <= cH, (
                                f"Zero-scroll failed at {w}x{h} ({tab_name}): "
                                f"scrollHeight ({sH}) > clientHeight ({cH})"
                            )
                            assert sW <= cW, (
                                f"Horizontal overflow at {w}x{h} ({tab_name}): "
                                f"scrollWidth ({sW}) > clientWidth ({cW})"
                            )
                        else:
                            # Mobile: no horizontal overflow
                            assert sW <= cW, (
                                f"Mobile horizontal overflow at {w}x{h} ({tab_name}): "
                                f"scrollWidth ({sW}) > clientWidth ({cW})"
                            )
        finally:
            proc.terminate()

    asyncio.run(run_checks())
