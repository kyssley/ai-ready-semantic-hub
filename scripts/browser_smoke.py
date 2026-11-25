"""Run against a disposable local --demo server; mutates its draft and published data."""

import os
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.getenv("CHROMIUM_EXECUTABLE"))
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(os.getenv("HUB_URL", "http://127.0.0.1:8000"))
        expect(page.locator(".stats")).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.locator('nav a[data-page="catalog"]').click()
        page.locator("#search").fill("seller_gmv")
        expect(page.locator('.entity[data-id="seller_gmv"]')).to_be_visible()
        page.locator('.entity[data-id="seller_gmv"]').click()
        expect(page.locator("#entityDetail")).to_contain_text("seller_net_amount")
        page.locator('nav a[data-page="graph"]').click()
        expect(page.locator("svg")).to_be_visible()
        page.locator('nav a[data-page="playground"]').click()
        page.locator("#exampleJoin").click()
        page.locator("#compile").click()
        expect(page.locator("#sqlOutput")).to_contain_text("LEFT JOIN")
        page.locator('nav a[data-page="context"]').click()
        page.locator("#buildContext").click()
        expect(page.locator("#contextResult")).to_contain_text("seller_gmv")
        page.locator('nav a[data-page="editor"]').click()
        editor = page.locator("#yamlEditor")
        expect(editor).to_be_visible()
        original = editor.input_value()
        editor.fill(original.replace("Commerce Intelligence", "Commerce Intelligence Reviewed"))
        page.locator("#validateYaml").click()
        expect(page.locator("#validationResult")).to_contain_text("Valid schema")
        page.locator("#changeMessage").fill("Browser smoke test")
        page.locator("#saveDraft").click()
        expect(page.locator("#toast")).to_contain_text("Draft saved")
        page.locator("#publishDraft").click()
        expect(page.locator("#workspaceName")).to_contain_text("Reviewed")
        page.locator('nav a[data-page="history"]').click()
        expect(page.locator("table")).to_contain_text("Browser smoke test")
        # Restore first revision as a draft without changing the publication.
        page.locator(".restore").last.click()
        expect(page.locator("#toast")).to_contain_text("Restored as a new draft")
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator('nav a[data-page="overview"]').click()
        expect(page.locator(".stats")).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not errors, errors
        browser.close()
    print(
        "Browser smoke passed: catalog, graph, compile, context, validate, save, publish, restore, mobile."
    )


if __name__ == "__main__":
    main()
