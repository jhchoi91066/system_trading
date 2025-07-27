
import asyncio
from playwright.async_api import async_playwright
import sys

async def get_readme_content(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            # Wait for a known element on the GitHub page to ensure it's loaded
            # Let's wait for the file list container to be visible
            await page.wait_for_selector('div[data-testid="directory-tree-container"]', timeout=30000)
            
            # The README content is within an article tag with the id "readme"
            readme_locator = page.locator('article#readme')
            
            if await readme_locator.count() > 0:
                content = await readme_locator.inner_text()
                print(content)
            else:
                print("ERROR: README element not found after page load.", file=sys.stderr)

        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
        finally:
            await browser.close()

if __name__ == "__main__":
    repo_url = "https://github.com/21st-dev/magic-mcp"
    asyncio.run(get_readme_content(repo_url))
