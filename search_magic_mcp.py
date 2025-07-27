
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/search?q=magic+mcp")

        # 검색 결과 링크 요소들을 찾습니다.
        # Google 검색 결과의 링크는 보통 'h3' 태그 안에 'a' 태그로 존재합니다.
        # (이 selector는 Google의 HTML 구조에 따라 변경될 수 있습니다.)
        links = page.locator('div.g a[href]')

        print("검색 결과:")
        for i in range(await links.count()):
            link = links.nth(i)
            href = await link.get_attribute('href')
            text = await link.inner_text()
            
            # 광고나 관련 없는 링크를 제외하기 위한 간단한 필터링
            if href and href.startswith('http') and text:
                print(f"- 제목: {text}")
                print(f"  URL: {href}")
                print("-" * 20)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
