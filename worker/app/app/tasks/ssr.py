import asyncio
import json

import time
import asyncio
import base64

import pyppeteer
import pyppeteer.browser
import pyppeteer.element_handle

from aioredis.client import Pipeline

from ..task_manager import get_db, queue_manager


MAX_PAGES = 3
MAX_BROWSER_IDLE = 5*60

running_workers = 0
browser = None
browser_closer: asyncio.Task = None

async def render(page:pyppeteer.browser.Page):
    db = get_db()
    xml = (db.task_dir / "tree.xml").read_text()
    db.msg = "Performing server-side render"
    db.total = None
    @db.transaction
    async def tx(pipe: Pipeline):
        pipe.multi()
        pipe.get(f"/tasks/{db.task_id}/stage/{db.stage}/info")
        pipe.get(f"/tasks/{db.task_id}/stage/{db.stage}/opts")
    data = await tx
    info = json.loads(data[-2])
    opts_override = json.loads(data[-1])

    scaleX = 0.4
    scaleY = 0.01183 * info["shape"][0]

    opts = {
        "dynamicHide": False,
        "height": 2000,
        "invertColors": False,
        "lineupNodes": True,
        "showDomains": False,
        "showDomainNames": False,
        "showDomainColors": True,
        "showGraphs": True,
        "showGraphLegend": True,
        "showLength": False,
        "showNodeNames": True,
        "showNodesType": "only leaf",
        "nodeHeight": 10,
        "origScaleX": scaleX,
        "scaleX": scaleX,
        "origScaleY": scaleY,
        "scaleY": scaleY,
        "scaleStep": 0.23,
        "margin": 100,
        "showPhylogram": True,
        "showTaxonomy": False,
        "showFullTaxonomy": False,
        "showSequences": False,
        "showLabels": False,
        "showTaxonomyColors": False,
        "backgroundColor": "#f5f5f5",
        "foregroundColor": "#000000",
        "nanColor": "#f5f5f5",
    }
    opts.update(opts_override)

    ttv = time.time()
    for attempt in range(30):
        try:
            await page.goto("http://web:8050/some_non_public_ssr_path")
            await page.waitForSelector("#loaded", timeout=30)
            break
        except Exception as e:
            if attempt == 29:
                raise
            await asyncio.sleep(1)
    print("page load took", time.time()-ttv)

    if info["kind"] == "png":
        ttv = time.time()
        fut = asyncio.Future()
        await page.exposeFunction("png_callback", fut.set_result)

        await page.evaluate(
            "(xml, opts) => {return window.build_tree_png(xml, opts)}",
            xml, opts,
        )
        res = base64.urlsafe_b64decode(await fut)
        print("took", time.time()-ttv)

        async with db.atomic_file(db.task_dir / "ssr_img.png") as tmp_file:
            with open(tmp_file, "wb") as f:
                f.write(res)
        print("ssr png done: ", res[:10])
    elif info["kind"] == "svg":
        ttv = time.time()
        svg = await page.evaluate(
            "(xml, opts) => {return window.build_tree(xml, opts)}",
            xml, opts,
        )
        print("took", time.time()-ttv)
        async with db.atomic_file(db.task_dir / "ssr_img.svg") as tmp_file:
            with open(tmp_file, "w") as f:
                f.write(svg)
        print("ssr svg done: ", svg[:10])

async def get_browser():
    global browser, browser_closer
    if browser_closer is not None:
        browser_closer.cancel()
        browser_closer = None
    if browser is None:
        browser = await pyppeteer.launch(
            executablePath="/usr/bin/chromium",
            headless=True,
            # devtools=True,
            autoClose=False,
            args=["--no-sandbox"],
            # dumpio=True,
        )
    return browser

async def close_unused_browser():
    global browser, browser_closer
    await asyncio.sleep(MAX_BROWSER_IDLE)
    if running_workers != 0:
        return
    br = browser
    browser = None
    browser_closer = None
    await br.close()


async def force_close_browser():
    global running_workers, browser, browser_closer
    try:
        await browser.close()
    except Exception:
        pass
    running_workers = 0
    if browser_closer:
        browser_closer.cancel()
        browser_closer = None

    browser = None




@queue_manager.add_handler("/queues/ssr", max_running=MAX_PAGES)
async def handler():
    """tasks come here"""
    db = get_db()
    global running_workers, browser_closer, browser
    page = None
    running_workers += 1
    try:
        for attempt in range(3):
            try:
                browser = await get_browser()
                page = await browser.newPage()
                break
            except Exception:
                await force_close_browser()
                if attempt == 2:
                    raise
        await render(page)
        await page.close()
    except Exception as e:
        try:
            await page.close()
        except Exception:
            await force_close_browser()
        raise e

    finally:
        if running_workers != 0: # not force-quit the browser
            running_workers -= 1
            if running_workers == 0:
                browser_closer = asyncio.create_task(close_unused_browser())

