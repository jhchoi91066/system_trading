
import asyncio
from playwright.async_api import async_playwright

async def get_readme_content(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until='networkidle')
            # GitHub README is usually in an article element with the id "readme"
            readme_locator = page.locator('article#readme')
            if await readme_locator.count() > 0:
                readme_html = await readme_locator.inner_html()
                print(readme_html)
            else:
                print("README not found on the page.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    repo_url = "https://github.com/21st-dev/magic-mcp"
    asyncio.run(get_readme_content(repo_url))
