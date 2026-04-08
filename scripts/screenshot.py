"""Take screenshots of all ERP IMS pages for README documentation."""
import asyncio
import os
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
OUT  = "docs/screenshots"
CHROME_EXECUTABLE = os.environ.get(
    "ERP_IMS_CHROME_PATH",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
LOGIN_USERNAME = os.environ.get("ERP_IMS_SCREENSHOT_USERNAME", "admin")
LOGIN_PASSWORD = os.environ.get("ERP_IMS_SCREENSHOT_PASSWORD", "admin12345")


class CaptureError(RuntimeError):
    """Raised when browser automation cannot continue safely."""


def field_selectors(fields: dict) -> list[str]:
    return list(fields.keys())


async def find_form_for_selector(page, selector: str):
    return page.locator("form", has=page.locator(selector)).first


async def submit_form(form):
    submit = form.locator('button[type="submit"], input[type="submit"]').first
    await submit.click()


async def ensure_logged_in(page, context: str):
    """Fail fast if the session has been redirected back to login."""
    await page.wait_for_load_state("domcontentloaded")
    current_url = page.url
    if "/login" in current_url:
        raise CaptureError(f"{context}: redirected to login at {current_url}")


async def fill_and_submit(page, url, fields: dict):
    """Navigate to URL, fill fields, submit. Returns True on success."""
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await ensure_logged_in(page, f"while opening seed form {url}")
        primary_field = field_selectors(fields)[0]
        await page.wait_for_selector(primary_field, timeout=5000)
        form = await find_form_for_selector(page, primary_field)
        for selector, value in fields.items():
            tag_name = await page.locator(selector).first.evaluate("(el) => el.tagName.toLowerCase()")
            if tag_name == "select":
                await page.select_option(selector, value=value)
            else:
                await page.fill(selector, value)
        await submit_form(form)
        await page.wait_for_load_state("domcontentloaded")
        return True
    except Exception as e:
        print(f"  (seed skip: {url} — {e})")
        return False


async def add_po_line(page, row_index: int, product_index: int, quantity: int, unit_cost: str):
    row = page.locator("#lines-body tr.line-row").nth(row_index)
    await row.locator('select[name="product_id[]"]').select_option(index=product_index)
    await row.locator('input[name="quantity[]"]').fill(str(quantity))
    await row.locator('input[name="unit_cost[]"]').fill(unit_cost)


async def create_purchase_order(page, supplier_index: int, warehouse_index: int, expected_at: str, lines: list[dict]):
    await page.goto(f"{BASE}/po/new", wait_until="domcontentloaded")
    await ensure_logged_in(page, "while opening purchase order form")
    await page.wait_for_selector('[name="supplier_id"]', timeout=5000)
    form = await find_form_for_selector(page, '[name="supplier_id"]')
    await page.select_option('[name="supplier_id"]', index=supplier_index)
    await page.select_option('[name="warehouse_id"]', index=warehouse_index)
    await page.fill('[name="expected_at"]', expected_at)

    for idx, line in enumerate(lines):
        if idx > 0:
            await page.click("#add-line")
            await page.wait_for_timeout(100)
        await add_po_line(page, idx, line["product_index"], line["quantity"], line["unit_cost"])

    await submit_form(form)
    await page.wait_for_load_state("domcontentloaded")
    await ensure_logged_in(page, "after creating purchase order")

    if "/po/" not in page.url:
        raise CaptureError(f"PO creation did not reach detail page: {page.url}")

    return page.url


async def submit_current_po(page):
    await page.wait_for_selector('form[action$="/submit"] button[type="submit"]', timeout=5000)
    await page.click('form[action$="/submit"] button[type="submit"]')
    await page.wait_for_load_state("domcontentloaded")
    await ensure_logged_in(page, "after submitting purchase order")


async def receive_current_po(page, quantities: list[int]):
    receive_href = await page.locator('a[href$="/receive"]').first.get_attribute("href")
    if not receive_href:
        raise CaptureError("receive page link not found for purchase order")

    await page.goto(f"{BASE}{receive_href}", wait_until="domcontentloaded")
    await ensure_logged_in(page, "while opening receive purchase order page")
    form = page.locator('form[action$="/receive"]').first
    for idx, qty in enumerate(quantities):
        if qty <= 0:
            continue
        await page.locator('input[type="number"]').nth(idx).fill(str(qty))
    await submit_form(form)
    await page.wait_for_load_state("domcontentloaded")
    await ensure_logged_in(page, "after receiving purchase order")


async def seed_data(page):
    print("Seeding sample data...")

    for name, location in [
        ("Taipei Main Warehouse", "Neihu District, Taipei"),
        ("Taoyuan Backup Warehouse", "Guishan District, Taoyuan"),
        ("Taichung Parts Warehouse", "Xitun District, Taichung"),
    ]:
        await fill_and_submit(page, f"{BASE}/warehouses/new", {
            '[name="name"]': name,
            '[name="location"]': location,
        })

    for supplier in [
        {
            "name": "Taiwan Electronic Components Co.",
            "contact_person": "David Wang",
            "email": "supply@example.com",
            "phone": "02-1234-5678",
        },
        {
            "name": "South China Industrial Materials Ltd.",
            "contact_person": "Ivy Lin",
            "email": "procurement@hn-materials.example",
            "phone": "03-5678-9000",
        },
        {
            "name": "Global Components Trading",
            "contact_person": "Kevin Liu",
            "email": "sales@global-components.example",
            "phone": "+886-4-2452-7788",
        },
    ]:
        await fill_and_submit(page, f"{BASE}/suppliers/new", {
            '[name="name"]': supplier["name"],
            '[name="contact_person"]': supplier["contact_person"],
            '[name="email"]': supplier["email"],
            '[name="phone"]': supplier["phone"],
        })

    for username, password, role in [
        ("warehouse.ops", "demo12345", "staff"),
        ("purchasing.lead", "demo12345", "admin"),
        ("auditor.team", "demo12345", "staff"),
    ]:
        await fill_and_submit(page, f"{BASE}/users/new", {
            '[name="username"]': username,
            '[name="password"]': password,
            '[name="role"]': role,
        })

    for sku, name, cost_price, reorder_point, description in [
        ("MCU-001", "STM32F103 Microcontroller", "25.50", "30", "Core controller used in main boards and sensor modules"),
        ("RES-100", "100 Ohm Resistor 1/4W", "0.35", "200", "Standard passive component for general assembly"),
        ("CAP-010", "10uF 25V Capacitor", "0.80", "120", "Used for power filtering and decoupling"),
        ("LED-RED", "Red LED 5mm", "1.20", "80", "Indicator light component for equipment panels"),
        ("PCB-001", "Main Control Board Rev 2.0", "120.00", "15", "Second production revision of the main board"),
        ("SEN-TMP", "Temperature Sensor Module", "48.00", "25", "Module for environment monitoring and alerts"),
        ("PWR-24V", "24V Power Supply Module", "210.00", "12", "Power module for industrial control equipment"),
        ("CASE-ALU", "Aluminum Enclosure", "95.00", "18", "Protective housing for the assembled device"),
    ]:
        await fill_and_submit(page, f"{BASE}/products/new", {
            '[name="sku"]': sku,
            '[name="name"]': name,
            '[name="unit"]':  "pcs",
            '[name="cost_price"]': cost_price,
            '[name="reorder_point"]': reorder_point,
            '[name="description"]': description,
        })

    for product_index, warehouse_index, mov, qty, note in [
        (1, 1, "in", "150", "Initial stock for Taipei main warehouse"),
        (2, 1, "in", "600", "First passive components shipment received"),
        (3, 1, "in", "320", "Capacitor stock initialized"),
        (4, 1, "in", "180", "LED components received into stock"),
        (5, 1, "in", "28", "First production batch completed"),
        (6, 2, "in", "55", "Backup stock prepared in Taoyuan"),
        (7, 2, "in", "20", "24V power modules received"),
        (8, 3, "in", "24", "Safety stock stored in Taichung"),
        (1, 1, "out", "45", "Engineering prototype build allocation"),
        (2, 1, "out", "180", "Production work order material issue"),
        (5, 1, "out", "6", "Finished goods moved to assembly"),
        (6, 2, "adjust_add", "4", "Cycle count positive adjustment"),
        (7, 2, "adjust_sub", "2", "Scrap deduction after inspection"),
        (8, 3, "transfer_out", "5", "Transferred to Taipei main warehouse"),
        (8, 1, "transfer_in", "5", "Received from Taichung parts warehouse"),
    ]:
        try:
            await page.goto(f"{BASE}/movements/new", wait_until="domcontentloaded")
            await ensure_logged_in(page, "while opening movement form")
            await page.wait_for_selector('[name="product_id"]', timeout=5000)
            await page.select_option('[name="product_id"]', index=product_index)
            await page.select_option('[name="warehouse_id"]', index=warehouse_index)
            await page.select_option('[name="movement_type"]', mov)
            await page.fill('[name="quantity"]', qty)
            await page.fill('[name="note"]', note)
            form = await find_form_for_selector(page, '[name="product_id"]')
            await submit_form(form)
            await page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            print(f"  (movement skip: {e})")

    try:
        await create_purchase_order(page, 1, 1, "2026-04-15", [
            {"product_index": 1, "quantity": 120, "unit_cost": "22.00"},
            {"product_index": 5, "quantity": 16, "unit_cost": "108.00"},
            {"product_index": 7, "quantity": 10, "unit_cost": "195.00"},
        ])
        await submit_current_po(page)
        await receive_current_po(page, [60, 8, 5])

        await create_purchase_order(page, 2, 2, "2026-04-18", [
            {"product_index": 2, "quantity": 1000, "unit_cost": "0.28"},
            {"product_index": 3, "quantity": 600, "unit_cost": "0.72"},
            {"product_index": 4, "quantity": 300, "unit_cost": "1.05"},
        ])
        await submit_current_po(page)

        await create_purchase_order(page, 3, 3, "2026-04-22", [
            {"product_index": 6, "quantity": 30, "unit_cost": "44.00"},
            {"product_index": 8, "quantity": 40, "unit_cost": "88.00"},
        ])
    except Exception as e:
        print(f"  (PO skip: {e})")

    print("Seed complete.\n")


async def screenshot(page, name, url, label, require_auth=True):
    await page.goto(f"{BASE}{url}", wait_until="domcontentloaded")
    if require_auth:
        await ensure_logged_in(page, f"while capturing {label}")
    await page.wait_for_timeout(500)
    await page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
    print(f"✓ {label}")


async def login(page):
    await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    await page.wait_for_selector('[name="csrf_token"]', timeout=5000, state="attached")
    form = await find_form_for_selector(page, '[name="username"]')
    await page.fill('[name="username"]', LOGIN_USERNAME)
    await page.fill('[name="password"]', LOGIN_PASSWORD)
    await submit_form(form)
    await page.wait_for_load_state("domcontentloaded")

    if "/dashboard" not in page.url:
        error_text = None
        error = page.locator(".alert-danger")
        if await error.count():
            error_text = (await error.first.inner_text()).strip()
        raise CaptureError(
            f"login failed; current_url={page.url}"
            + (f"; error={error_text}" if error_text else "")
        )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROME_EXECUTABLE,
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Login page (unauthenticated)
        await screenshot(page, "01_login", "/login", "登入頁面", require_auth=False)

        # Authenticate
        await login(page)

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
