"""Take screenshots of all ERP IMS pages for README documentation."""
import asyncio
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
OUT  = "docs/screenshots"


async def fill_and_submit(page, url, fields: dict):
    """Navigate to URL, fill fields, submit. Returns True on success."""
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_selector('button[type="submit"]', timeout=5000)
        for selector, value in fields.items():
            await page.fill(selector, value)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("domcontentloaded")
        return True
    except Exception as e:
        print(f"  (seed skip: {url} — {e})")
        return False


async def seed_data(page):
    print("Seeding sample data...")

    await fill_and_submit(page, f"{BASE}/warehouses/new", {
        '[name="name"]': "台北主倉",
        '[name="location"]': "台北市內湖區",
    })

    await fill_and_submit(page, f"{BASE}/suppliers/new", {
        '[name="name"]': "台灣電子零件有限公司",
        '[name="contact_person"]': "王大明",
        '[name="email"]': "supply@example.com",
        '[name="phone"]': "02-1234-5678",
    })

    for sku, name in [
        ("MCU-001", "微控制器 STM32F103"),
        ("RES-100", "電阻 100Ω 1/4W"),
        ("CAP-010", "電容 10uF 25V"),
        ("LED-RED", "LED 紅色 5mm"),
        ("PCB-001", "主控板 Rev2.0"),
    ]:
        await fill_and_submit(page, f"{BASE}/products/new", {
            '[name="sku"]':   sku,
            '[name="name"]':  name,
            '[name="unit"]':  "pcs",
            '[name="cost_price"]': "25.50",
            '[name="reorder_point"]': "10",
        })

    # Add stock movements
    for qty, note in [("150", "初始庫存建立"), ("80", "第二批進貨"), ("30", "生產領料出庫")]:
        try:
            await page.goto(f"{BASE}/movements/new", wait_until="domcontentloaded")
            await page.wait_for_selector('[name="product_id"]', timeout=5000)
            await page.select_option('[name="product_id"]', index=1)
            await page.select_option('[name="warehouse_id"]', index=1)
            mov = "in" if note != "生產領料出庫" else "out"
            await page.select_option('[name="movement_type"]', mov)
            await page.fill('[name="quantity"]', qty)
            await page.fill('[name="note"]', note)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            print(f"  (movement skip: {e})")

    # Create a purchase order
    try:
        await page.goto(f"{BASE}/po/new", wait_until="domcontentloaded")
        await page.wait_for_selector('[name="supplier_id"]', timeout=5000)
        await page.select_option('[name="supplier_id"]', index=1)
        await page.select_option('[name="warehouse_id"]', index=1)
        await page.fill('[name="notes"]', "季度採購計畫")
        # Add a line item if the form supports it
        try:
            await page.select_option('[name="product_id[]"]', index=1)
            await page.fill('[name="quantity_ordered[]"]', "100")
            await page.fill('[name="unit_cost[]"]', "22.00")
        except Exception:
            pass
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("domcontentloaded")
    except Exception as e:
        print(f"  (PO skip: {e})")

    print("Seed complete.\n")


async def screenshot(page, name, url, label):
    await page.goto(f"{BASE}{url}", wait_until="domcontentloaded")
    await page.wait_for_timeout(500)
    await page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
    print(f"✓ {label}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Login page (unauthenticated)
        await screenshot(page, "01_login", "/login", "登入頁面")

        # Authenticate
        await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        await page.fill('[name="username"]', "admin")
        await page.fill('[name="password"]', "admin12345")
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("domcontentloaded")

        # Seed data
        await seed_data(page)

        # Take all screenshots
        pages = [
            ("02_dashboard",       "/dashboard",       "儀表板"),
            ("03_products_list",   "/products",        "商品列表"),
            ("04_product_new",     "/products/new",    "新增商品"),
            ("05_movements_list",  "/movements",       "庫存異動紀錄"),
            ("06_movement_new",    "/movements/new",   "新增異動"),
            ("07_suppliers_list",  "/suppliers",       "供應商列表"),
            ("08_supplier_new",    "/suppliers/new",   "新增供應商"),
            ("09_warehouses_list", "/warehouses",      "倉庫管理"),
            ("10_po_list",         "/po",              "採購單列表"),
            ("11_po_new",          "/po/new",          "新增採購單"),
            ("12_users_list",      "/users",           "使用者管理"),
        ]

        for name, url, label in pages:
            await screenshot(page, name, url, label)

        # Product detail (first product)
        try:
            await page.goto(f"{BASE}/products", wait_until="domcontentloaded")
            link = page.locator("table tbody tr:first-child a").first
            href = await link.get_attribute("href")
            if href:
                await screenshot(page, "04b_product_detail", href, "商品詳情")
        except Exception:
            pass

        await browser.close()
        print(f"\nAll screenshots saved to {OUT}/")


asyncio.run(main())
