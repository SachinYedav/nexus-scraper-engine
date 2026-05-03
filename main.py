from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import urllib.parse
import re
import uuid
import json
import time
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

class ExtractRequest(BaseModel):
    url: str
    source: str
    mode: Optional[str] = "packs" # Default "packs"

# ==========================================
# 🌐 GLOBAL BROWSER MANAGEMENT (MEMORY SAFE & STEALTH)
# ==========================================
_playwright_instance = None
_browser_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _playwright_instance, _browser_instance
    print("🚀 [System] Starting Global Playwright Browser in Stealth Mode...")
    _playwright_instance = await async_playwright().start()

    # Docker/Linux & Anti-Bot Stealth Arguments
    _browser_instance = await _playwright_instance.chromium.launch(
        headless=True, # Background process
        args=[
            "--headless=new",
            "--disable-blink-features=AutomationControlled", # Anti-bot bypass
            "--no-sandbox", # Crucial for Docker/Linux deployments
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage" # Prevents Out of Memory (OOM) crashes
        ]
    )
    print("✅ [System] Shared Stealth Browser is Ready!")

    yield # App runs here

    print("🛑 [System] Shutting down Global Browser safely...")
    if _browser_instance:
        await _browser_instance.close()
    if _playwright_instance:
        await _playwright_instance.stop()

# App Initialization with Lifespan
app = FastAPI(title="Ultimate Movie Scraper API", lifespan=lifespan)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS Setup for Frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_browser():
    """Returns the globally running browser instance initialized during startup"""
    global _browser_instance
    if not _browser_instance or not _browser_instance.is_connected():
        print("⚠️ [System] Browser disconnected! Throwing error.")
        raise HTTPException(status_code=500, detail="Browser instance lost. Please restart server.")
    return _browser_instance


# ==========================================
# 🟣 9XFLIX LOGIC MODULE (SMART ENGINE)
# ==========================================
async def search_9xflix(query, limit: int = 4):
    search_term = query.replace(" ", "+")
    base_domain = "https://9xflix.eu"
    target_url = f"{base_domain}/m/?s={search_term}"
    results = []

    print(f"🔍 [9xFlix] Searching for: '{query}'...")

    browser = await get_browser()
    page = await browser.new_page()

    # Block ads to make search lightning fast
    await page.route("**/*", block_ads_and_popups)

    try:
        await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        wrappers = await page.query_selector_all('.imag, li, .post-item')

        for wrapper in wrappers:
            title_link = await wrapper.query_selector('h2.entry-title a, article a')

            if title_link:
                href = await title_link.get_attribute('href')
                title = await title_link.inner_text()

                if href and title and '9xflix' in href:
                    clean_title = title.strip()

                    if len(clean_title) > 5:
                        raw_img_url = await wrapper.evaluate('''el => {
                            let img = el.querySelector('img');
                            if (img) {
                                let src = img.getAttribute('data-lazy-src') || img.getAttribute('data-src') || img.getAttribute('src') || img.src;
                                if (src && !src.startsWith('data:image')) return src;
                            }
                            return null;
                        }''')

                        img_url = urllib.parse.urljoin(base_domain, raw_img_url) if raw_img_url else "https://placehold.co/300x450/111827/e5e7eb?text=No+Movie+Poster"

                        if not any(res['url'] == href for res in results):
                            results.append({
                                "title": clean_title,
                                "url": href,
                                "image": img_url,
                                "source": "9xflix"
                            })

                        if len(results) >= limit: break
    except Exception as e:
        print(f"❌ [9xFlix] Search Error: {e}")
    finally:
        await page.close()

    return results


async def _crack_desilinks(page, desilink_url):
    """Layer 2: Extract real hosting servers from Desilinks"""
    try:
        await page.goto(desilink_url, timeout=40000, wait_until="domcontentloaded")
        await asyncio.sleep(1)

        server_links = await page.evaluate('''() => {
            let results = {};
            // Ignore dead servers completely
            let deadServers = ['zippyshare', 'bayfiles', 'sharer.pw'];
            let links = document.querySelectorAll('.entry-content a');

            for (let a of links) {
                let href = a.href || '';
                if (!href.startsWith('http')) continue;

                let urlLower = href.toLowerCase();
                if (deadServers.some(dead => urlLower.includes(dead))) continue;

                if (urlLower.includes('gofile')) results['📂 GoFile (Fast)'] = href;
                else if (urlLower.includes('send.cm')) results['☁️ Send.cm'] = href;
                else if (urlLower.includes('1fichier')) results['⚡ 1Fichier'] = href;
                else if (urlLower.includes('indishare')) results['🇮🇳 IndiShare'] = href;
                else if (urlLower.includes('bdupload')) results['⬆️ BDUpload'] = href;
                else {
                    try {
                        let domain = new URL(href).hostname.replace('www.', '').split('.')[0];
                        let cleanName = domain.charAt(0).toUpperCase() + domain.slice(1);
                        results[`🔗 ${cleanName}`] = href;
                    } catch(e) {}
                }
            }
            return results;
        }''')
        return server_links
    except Exception as e:
        print(f"      [Error] Failed to decode Desilinks: {e}")
        return {}


async def extract_9xflix(detail_url: str):
    """Layer 1: Main 9xFlix Extractor"""
    print(f"\n🎬 [9xFlix] Deep Extraction Started for: {detail_url}")
    final_links = {}

    browser = await get_browser()
    context = await browser.new_context()
    page = await context.new_page()
    await page.route("**/*", block_ads_and_popups)

    try:
        await page.goto(detail_url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # 🧠 Smart Extractor: Ignored torrents and gets real Desilinks URL immediately
        layer1_data = await page.evaluate('''() => {
            let results = {};
            let links = document.querySelectorAll('.entry.clearfix a, .entry-content a');

            for (let a of links) {
                let text = (a.innerText || '').toUpperCase().trim();
                let href = a.href || '';

                if (text.includes('TORRENT') || href.includes('magnet:')) continue;

                if (text.match(/\\d{3,4}P/) || text.includes('4K')) {
                    let finalUrl = href;

                    // Directly parse open/?url= redirectors to save time
                    if (href.includes('open/?url=')) {
                        try {
                            let urlObj = new URL(href);
                            let params = new URLSearchParams(urlObj.search);
                            if (params.has('url')) finalUrl = params.get('url');
                        } catch (e) {}
                    }
                    let cleanName = text.replace(/\\n/g, '').trim();
                    if (!results[cleanName]) results[cleanName] = finalUrl;
                }
            }
            return results;
        }''')

        if not layer1_data:
            print("⚠️ No valid download links found on 9xFlix.")
            return final_links

        print(f"🎯 Found {len(layer1_data)} valid packs! Bypassing Desilinks...")

        for pack_name, desilink_url in layer1_data.items():
            if 'desilinks' in desilink_url.lower():
                server_dict = await _crack_desilinks(page, desilink_url)
                if server_dict:
                    for srv_name, srv_url in server_dict.items():
                        # UI ke Smart Sorter ke liye 'Pack' tag add kiya
                        final_links[f"Pack [{pack_name}] ➔ {srv_name}"] = srv_url
            else:
                final_links[f"Pack [{pack_name}] ➔ ⚡ Direct Link"] = desilink_url

    except Exception as e:
        print(f"❌ [9xFlix] Extraction Error: {e}")
    finally:
        await context.close()

    return final_links

# ==========================================
# 🟣 HDHUB4U LOGIC MODULE
# ==========================================
BASE_URL_HD = "https://new7.hdhub4u.fo"

async def search_hdhub(query, limit: int = 4):
    search_term = query.replace(" ", "+")
    target_url = f"{BASE_URL_HD}/search.html?q={search_term}"
    results = []

    print(f"🔍 [HDHub4u] Searching for: '{query}'...")
    browser = await get_browser()
    page = await browser.new_page()

    try:
        try:
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as goto_err:
            if "ERR_ABORTED" not in str(goto_err): raise goto_err

        await asyncio.sleep(5)
        all_links = await page.query_selector_all('a')

        for link in all_links:
            href = await link.get_attribute('href')
            text_clean = await link.evaluate("el => el.innerText || el.textContent")

            img_url = await link.evaluate('''el => {
                let img = el.querySelector('img') || (el.closest('article, .item, figure, .post') && el.closest('article, .item, figure, .post').querySelector('img'));
                return img ? (img.getAttribute('data-src') || img.src) : "https://placehold.co/300x450/111827/e5e7eb?text=No+Movie+Poster";
            }''')

            if href and text_clean:
                text_clean = text_clean.strip()
                if len(text_clean) > 5 and 'search.html' not in href and 'javascript' not in href:
                    absolute_url = urllib.parse.urljoin(BASE_URL_HD, href)
                    if absolute_url != BASE_URL_HD and absolute_url != f"{BASE_URL_HD}/":
                        if not any(res['url'] == absolute_url for res in results):
                            results.append({
                                "title": text_clean.replace('\n', ' '),
                                "url": absolute_url,
                                "image": img_url,
                                "source": "hdhub4u"
                            })
                        if len(results) >= limit: break
    except Exception as e:
        print(f"❌ [HDHub4u] Search Error: {e}")
    finally:
        await page.close()

    return results

# ==========================================
# 🛑 SMART AD & POPUP BLOCKER
# ==========================================
async def block_ads_and_popups(route, request):
    """Network level ad-blocker for faster and crash-free execution"""
    bad_domains = ['adsboosters.xyz', 'cloudfront.net', 'cloudflareinsights.com', 'greenanalytics', 'popads', 'winexch.com']
    if any(domain in request.url for domain in bad_domains) or request.resource_type in ['image', 'media', 'font']:
        await route.abort()
    else:
        await route.continue_()

# ==========================================
# 🟣 HDHUB4U GATEWAY CRACKER (ALL 5 LAYERS)
# ==========================================
async def _crack_hub_gateway(page, current_url):
    """Layer 3, 4 & 5 Bypass - Domain Aware Routing & Native API Extraction"""
    results = {}
    url_lower = current_url.lower()

    # ------------------------------------------
    # LAYER 1: GATEWAY ROUTING (hblinks.dad)
    # ------------------------------------------
    if 'hblinks' in url_lower:
        print(f"      [Routing] Gateway detected. Extracting real server...")
        try:
            await page.goto(current_url, timeout=40000, wait_until="domcontentloaded")
            await asyncio.sleep(1.5)

            target_url = await page.evaluate('''() => {
                let links = Array.from(document.querySelectorAll('a'));
                let premium = links.find(a => a.href.includes('/file/'));
                let cloud = links.find(a => a.href.includes('/drive/'));
                let gofile = links.find(a => a.href.includes('gofile'));

                if(premium) return premium.href;
                if(cloud) return cloud.href;
                if(gofile) return gofile.href;
                return null;
            }''')

            if target_url:
                current_url = target_url
                url_lower = current_url.lower()
            else:
                return {"⚠️ Direct Link": current_url}

        except Exception as e:
            print(f"      [Error] Gateway bypass failed: {e}")
            return {"⚠️ Gateway Error": current_url}

    # ------------------------------------------
    # LAYER 2 & 3: SERVER CRACKING
    # ------------------------------------------
    if 'hubcdn' in url_lower or 'hubdrive' in url_lower:
        print("      [Crack] Processing Premium Drive (Native Python API)...")
        try:
            await page.goto(current_url, timeout=40000, wait_until="domcontentloaded")
            await asyncio.sleep(1)

            id_val = await page.evaluate('() => { let el = document.querySelector("#down-id"); return el ? el.innerText.trim() : null; }')

            if id_val:
                parsed_url = urllib.parse.urlparse(current_url)
                ajax_url = f"{parsed_url.scheme}://{parsed_url.netloc}/ajax.php?ajax=direct-download"

                req_context = page.context.request
                response = await req_context.post(
                    ajax_url,
                    form={"id": id_val},
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": current_url,
                        "User-Agent": await page.evaluate("navigator.userAgent")
                    }
                )

                json_data = await response.json()
                if json_data and str(json_data.get("code")) == "200":
                    results['⚡ VIP Direct'] = json_data.get("data")
                else:
                    results['⚡ Premium Link'] = current_url
            else:
                results['⚡ Instant Link'] = current_url
        except Exception as e:
            print(f"      [Error] Premium Drive crack failed: {e}")
            results['⚡ Premium Fallback'] = current_url

    elif 'hubcloud' in url_lower:
        print("      [Crack] Processing HubCloud (Token Bypass)...")
        try:
            await page.goto(current_url, timeout=40000, wait_until="domcontentloaded")
            await asyncio.sleep(1)

            token_url = await page.evaluate("() => { let el = document.querySelector('a#download'); return el ? el.href : null; }")

            if token_url:
                await page.goto(token_url, timeout=40000, wait_until="domcontentloaded")
                print("      [Wait] Waiting 3s for Fake-Links to swap...")
                await asyncio.sleep(3) # Crucial: Let the fake links swap to real servers

                final_data = await page.evaluate('''() => {
                    let data = {};
                    let links = Array.from(document.querySelectorAll('a'));

                    let pxl = links.find(a => a.id === 'pxl-1' || a.innerText.toLowerCase().includes('pixel') || a.href.includes('pixeldrain'));
                    if (pxl) {
                        data['🔥 PixelDrain'] = pxl.href;
                    }

                    let g10 = links.find(a => a.innerText.toLowerCase().includes('10gbps'));
                    if (g10) data['🚀 10Gbps'] = g10.href;

                    return data;
                }''')

                if final_data and len(final_data) > 0:
                    results.update(final_data)
                else:
                    results['☁️ HubCloud Direct'] = current_url
            else:
                results['☁️ HubCloud Token Link'] = current_url
        except Exception as e:
            print(f"      [Error] HubCloud crack failed: {e}")
            results['☁️ HubCloud Error'] = current_url

    elif 'gofile' in url_lower:
        print("      [Crack] Processing GoFile...")
        results['📂 GoFile'] = current_url

    else:
        results['🔗 Source Link'] = current_url

    return results


# ==========================================
# 🟣 HDHUB4U MAIN EXTRACTOR (WITH FETCH MODE)
# ==========================================
async def extract_hdhub(detail_url: str, fetch_mode: str = "packs"):
    """fetch_mode can be 'packs', 'episodes', or 'all'"""
    print(f"\n🎬 [HDHub4u] Extraction Started ({fetch_mode.upper()} mode): {detail_url}")
    final_links = {}

    browser = await get_browser()
    context = await browser.new_context()
    page = await context.new_page()

    # Block ads for extreme speed
    await page.route("**/*", block_ads_and_popups)

    try:
        await page.goto(detail_url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # 🧠 HYBRID DOM PARSER WITH ON-DEMAND FILTERING
        qualities = await page.evaluate(f'''() => {{
            let results = {{}};
            let currentEpi = "Movie / Pack";
            let currentQuality = "480p";
            let mode = "{fetch_mode}";

            // Failsafe Selectors
            let elements = document.querySelectorAll('.page-body h1, .page-body h2, .page-body h3, .page-body h4, .page-body p, .page-body a, .entry-content h1, .entry-content h2, .entry-content h3, .entry-content h4, .entry-content p, .entry-content a');

            if(elements.length === 0) {{
                elements = document.querySelectorAll('h1, h2, h3, h4, p, a');
            }}

            for (let el of elements) {{
                let text = (el.innerText || '').toUpperCase().trim();
                let tagName = el.tagName.toUpperCase();

                // Track Episode Context
                if (text.includes('EPISODE')) {{
                    let match = text.match(/EPISODE\\s*\\d+/);
                    if (match && tagName !== 'A') {{
                        currentEpi = match[0];
                    }}
                }}

                // Track Quality Context
                if (text.includes('1080P') || text.includes('1080')) currentQuality = '1080p';
                else if (text.includes('720P') || text.includes('720')) currentQuality = '720p';
                else if (text.includes('480P') || text.includes('480')) currentQuality = '480p';
                else if (text.includes('2160P') || text.includes('4K') || text.includes('2160')) currentQuality = '4K';

                // Process Valid Download Links
                if (tagName === 'A' && el.href) {{
                    let href = el.href.toLowerCase();
                    let linkText = text.toLowerCase();

                    let isTarget = href.includes('hubcloud') || href.includes('hubcdn') || href.includes('hblinks') || href.includes('hubdrive') || href.includes('gofile');

                    if (isTarget && !linkText.includes('telegram') && !linkText.includes('how to')) {{

                        let isEpisodeLink = currentEpi !== "Movie / Pack" && (linkText.includes('drive') || linkText.includes('instant') || linkText.includes('watch'));

                        // 🧠 OPTIMIZATION FILTER
                        if (mode === "packs" && isEpisodeLink) continue;
                        if (mode === "episodes" && !isEpisodeLink) continue;

                        let parentText = el.parentElement ? (el.parentElement.innerText || '').toUpperCase() : '';
                        let combinedText = parentText + " " + text;

                        if (isEpisodeLink) {{
                            let type = linkText.includes('instant') ? 'Instant' : 'Drive';
                            let key = `${{currentEpi}} [${{currentQuality}}] [${{type}}]`;
                            if (!results[key]) results[key] = el.href;
                        }}
                        else {{
                            let specificQ = currentQuality;
                            if (combinedText.includes('1080')) specificQ = '1080p';
                            else if (combinedText.includes('720')) specificQ = '720p';
                            else if (combinedText.includes('4K') || combinedText.includes('2160')) specificQ = '4K';

                            let sizeMatch = combinedText.match(/\\d+(\\.\\d+)?\\s*(MB|GB)/);
                            let size = sizeMatch ? ` - ${{sizeMatch[0]}}` : '';

                            let key = `Pack [${{specificQ}}${{size}}]`;
                            if (!results[key]) results[key] = el.href;
                        }}
                    }}
                }}
            }}
            return results;
        }}''')

        if not qualities:
            print(f"⚠️ No links found for mode: {fetch_mode}")
            return final_links

        print(f"🎯 Found {len(qualities)} target links for {fetch_mode}! Extracting...")

        for quality_name, gateway_url in qualities.items():
            print(f"⏳ Processing: {quality_name}")
            cracked_dict = await _crack_hub_gateway(page, gateway_url)

            if cracked_dict:
                for srv_name, srv_url in cracked_dict.items():
                    ui_key = f"{quality_name} ➔ {srv_name}"
                    if ui_key not in final_links:
                        final_links[ui_key] = srv_url
                print(f"   🏆 Secured!")
            else:
                print(f"   ⚠️ Fallback applied.")
                final_links[f"{quality_name} ➔ ⚠️ Gateway"] = gateway_url

    except Exception as e:
        print(f"❌ [HDHub4u] Master Extraction Error: {e}")
    finally:
        await context.close()

    return final_links

# ==========================================
# 🟢 FILMYPARDA SCRAPING ENGINE
# ==========================================
FILMYPARDA_DOMAIN = "https://filmyparda.com"

async def search_filmyparda(query: str, limit: int):
    """Advanced Search for Filmyparda with Fallbacks"""
    search_term = query.replace(" ", "+")
    target_url = f"{FILMYPARDA_DOMAIN}/index.php?do=search&subaction=search&story={search_term}"
    results = []

    try:
        browser = await get_browser()
        page = await browser.new_page()
        await page.route("**/*", block_ads_and_popups)

        await page.goto(target_url, timeout=40000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        items = await page.query_selector_all('li:has(a[href])')

        # Fallback to UI search if direct URL fails
        if not items:
            await page.goto(FILMYPARDA_DOMAIN, timeout=40000, wait_until="domcontentloaded")
            await page.fill('input[placeholder*="Search"]', query)
            await asyncio.sleep(1)
            search_btn = await page.query_selector('button:has-text("Search")')
            if search_btn: await search_btn.click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)
            items = await page.query_selector_all('li:has(a[href])')

        for item in items:
            link_el = await item.query_selector('a')
            if not link_el: continue
            href = await link_el.get_attribute('href')

            if not href or 'filmyparda.com' not in href or href == f"{FILMYPARDA_DOMAIN}/":
                continue

            title_text = await item.evaluate("el => { let p = el.querySelector('p'); return p ? (p.innerText || p.textContent) : null; }")
            raw_img_url = await item.evaluate("el => { let img = el.querySelector('img'); return img ? (img.getAttribute('data-src') || img.src) : null; }")

            if href and title_text:
                clean_title = ' '.join(title_text.replace('\n', ' ').split())
                img_url = urllib.parse.urljoin(FILMYPARDA_DOMAIN, raw_img_url) if raw_img_url else "https://placehold.co/300x450/111827/e5e7eb?text=No+Movie+Poster"

                if not any(res['url'] == href for res in results):
                    results.append({
                        "title": clean_title,
                        "url": href,
                        "image": img_url,
                        "source": "Filmyparda"
                    })

                    if len(results) >= limit: break  # fetch Top 2 results

        await page.close()
    except Exception as e:
        print(f"❌ [Filmyparda] Search Error: {e}")

    return results

async def _bypass_fast_dl_helper(context, fast_dl_url: str):
    """Extreme Ad-Blocking Bypass Helper for Fast-DL"""
    page = await context.new_page()
    final_url = None
    download_event = asyncio.Event()

    async def on_download(download):
        nonlocal final_url
        final_url = download.url
        await download.cancel()
        download_event.set()

    page.on("download", on_download)

    try:
        await page.goto(fast_dl_url, timeout=40000, wait_until="domcontentloaded")

        # 1. Verify Phase
        verify_btn = page.locator('text="Click to verify"').first
        await verify_btn.wait_for(state="visible", timeout=15000)
        await verify_btn.scroll_into_view_if_needed()

        try:
            async with context.expect_page(timeout=2000) as ad_info:
                await verify_btn.click()
            await (await ad_info.value).close()
            await verify_btn.click()
        except Exception:
            pass

        # 2. Download Phase
        next_btn = page.locator('button, a').filter(has_text="Download").first
        await next_btn.wait_for(state="visible", timeout=15000)
        await next_btn.scroll_into_view_if_needed()
        await asyncio.sleep(1)

        try:
            async with context.expect_page(timeout=2000) as ad_info:
                await next_btn.click(force=True)
            await (await ad_info.value).close()
        except Exception:
            pass

        if not download_event.is_set():
            await next_btn.click(force=True)

        try:
            await asyncio.wait_for(download_event.wait(), timeout=45.0)
        except asyncio.TimeoutError:
            print(f"⚠️ [Fast-DL] Server timeout for {fast_dl_url}")

    except Exception as e:
        print(f"❌ [Fast-DL] Bypass failed: {e}")
    finally:
        await page.close()

    return final_url

async def extract_filmyparda(detail_url: str):
    """Extracts qualities and bypasses links for Filmyparda"""
    final_links = {}

    try:
        browser = await get_browser()
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(detail_url, timeout=40000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        all_links = await page.query_selector_all('a')
        fast_dl_links = {}

        for link in all_links:
            href = await link.get_attribute('href')
            if not href or href == '#' or 'javascript' in href.lower(): continue

            text = await link.evaluate("el => (el.innerText || el.textContent)")
            if not text: continue

            text_lower = text.strip().lower()
            if 'download' in text_lower and ('mb' in text_lower or 'gb' in text_lower):
                quality = None
                if '1080p' in text_lower: quality = '1080p'
                elif '720p' in text_lower: quality = '720p'
                elif '480p' in text_lower: quality = '480p'

                if quality and quality not in fast_dl_links:
                    fast_dl_links[quality] = urllib.parse.urljoin(detail_url, href)

        # Process bypasses sequentially to avoid overwhelming the network/browser
        for quality, fast_dl_url in fast_dl_links.items():
            direct_link = await _bypass_fast_dl_helper(context, fast_dl_url)
            if direct_link:
                final_links[quality] = direct_link

        await context.close()
    except Exception as e:
        print(f"❌ [Filmyparda] Extraction Error: {e}")

    return final_links

# ==========================================
# 🟢 FILMYFLY SCRAPING ENGINE
# ==========================================
BASE_URL_FILMYFLY = "https://1filmyfly.dad"

async def search_filmyfly(query: str, limit: int):
    search_term = query.replace(" ", "+")
    target_url = f"{BASE_URL_FILMYFLY}/site-1.html?to-search={search_term}"
    results = []

    print(f"🔍 [FilmyFly] Searching for: '{query}'...")

    browser = await get_browser()
    page = await browser.new_page()

    # AD-BLOCKER INJECTED TO PREVENT FREEZES
    await page.route("**/*", block_ads_and_popups)

    try:
        await page.goto(target_url, timeout=40000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        items = await page.query_selector_all('div:has(a[href*="/page-download/"])')

        for item in items:
            try:
                raw_title = await item.evaluate("el => el.innerText || el.textContent")
                clean_title = ' '.join(raw_title.replace('\n', ' ').split()).strip()

                link_el = await item.query_selector('a[href*="/page-download/"]')
                if not link_el: continue
                href = await link_el.get_attribute('href')
                absolute_url = urllib.parse.urljoin(BASE_URL_FILMYFLY, href)

                raw_img_url = await item.evaluate('''el => {
                    let img = el.querySelector('img');
                    return img ? (img.getAttribute('data-src') || img.src) : null;
                }''')

                if raw_img_url:
                    # 🎯 The CDN Hack for High Quality Images
                    import re
                    hq_img_url = re.sub(r'/\d+:\d+/', '/350:500/', raw_img_url)
                    img_url = urllib.parse.urljoin(BASE_URL_FILMYFLY, hq_img_url)
                else:
                    img_url = "https://placehold.co/300x450/111827/e5e7eb?text=No+Poster"

                if absolute_url and clean_title:
                    if not any(res['url'] == absolute_url for res in results):
                        results.append({
                            "title": clean_title,
                            "url": absolute_url,
                            "image": img_url,
                            "source": "filmyfly"
                        })

                if len(results) >= limit: break
            except Exception as item_err:
                continue

    except Exception as e:
        print(f"❌ [FilmyFly] Search Error: {e}")
    finally:
        await page.close()

    return results

async def extract_filmyfly(detail_url: str):
    print(f"🎬 [FilmyFly] Deep Extraction Started for: {detail_url}")
    final_links = {}

    browser = await get_browser()
    context = await browser.new_context()
    page = await context.new_page()

    #  AD-BLOCKER INJECTED
    await page.route("**/*", block_ads_and_popups)

    try:
        # ==========================================
        # LAYER 2: Master Download Button
        # ==========================================
        await page.goto(detail_url, timeout=40000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        all_links = await page.query_selector_all('a')
        linkmake_url = None

        for link in all_links:
            text = await link.evaluate("el => el.innerText || el.textContent")
            if not text: continue

            text_lower = text.strip().lower()
            href = await link.get_attribute('href')

            # 🎯 Bulletproof Matcher for Both Movies & Web Series
            if href and 'download' in text_lower:
                if any(res in text_lower for res in ['480p', '720p', '1080p', '2160p', 'episodes', 'zip', 'pack']):
                    linkmake_url = urllib.parse.urljoin(BASE_URL_FILMYFLY, href)
                    break

        if not linkmake_url:
            print("❌ [FilmyFly] Master Download button not found!")
            return final_links

        # ==========================================
        # LAYER 2.5: Link Protector & Quality Extraction
        # ==========================================
        await page.goto(linkmake_url, timeout=40000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        protector_links = await page.query_selector_all('.dlink a')
        if not protector_links:
            protector_links = await page.query_selector_all('a')

        quality_links = {}
        for link in protector_links:
            try:
                href = await link.get_attribute('href')
                text = await link.evaluate("el => (el.innerText || el.textContent)")

                if href and text:
                    text_lower = text.strip().lower()

                    q_key = None
                    if '2160p' in text_lower or '4k' in text_lower: q_key = '2160p'
                    elif '1080p' in text_lower: q_key = '1080p'
                    elif '720p' in text_lower: q_key = '720p'
                    elif '480p' in text_lower: q_key = '480p'
                    elif 'episodes' in text_lower or 'zip' in text_lower: q_key = 'pack'

                    if q_key and q_key not in quality_links:
                        quality_links[q_key] = href
            except: continue

        # ==========================================
        # LAYER 3: JS Token Bypass & Smart Fallback Filter
        # ==========================================
        for quality, target_url in quality_links.items():
            try:
                # 'networkidle' is CRITICAL here for the JS token generation
                await page.goto(target_url, timeout=50000, wait_until="networkidle")
                await asyncio.sleep(1)

                all_buttons = await page.query_selector_all('.container a')

                direct_links = {}
                fallback_links = {}

                for btn in all_buttons:
                    text = await btn.evaluate("el => (el.innerText || el.textContent)")
                    href = await btn.evaluate("el => el.href") # Execute JS and get token URL

                    if not text or not href: continue
                    text_lower = text.strip().lower()

                    # Categorize Links
                    if 'cloud direct' in text_lower or 'fast direct' in text_lower or 'fdownload' in href:
                        direct_links['⚡ Fast Direct'] = href
                    elif 'pixeldrain' in text_lower:
                        direct_links['🔥 PixelDrain'] = href
                    elif 'gofile' in text_lower:
                        fallback_links['📂 GoFile'] = href
                    elif 'hubcloud' in text_lower:
                        fallback_links['☁️ HubCloud'] = href
                    elif 'buzz' in text_lower:
                        fallback_links['🐌 Buzz Backup'] = href

                # 🧠 SMART UI FILTER
                if direct_links:
                    # Give only the best direct link, ignore clutter
                    best_name = list(direct_links.keys())[0]
                    final_links[f"Pack [{quality.upper()}] ➔ {best_name}"] = direct_links[best_name]
                elif fallback_links:
                    # Only show fallbacks if direct fails
                    best_name = list(fallback_links.keys())[0]
                    final_links[f"Pack [{quality.upper()}] ➔ {best_name}"] = fallback_links[best_name]

            except Exception as q_err:
                print(f"⚠️ [FilmyFly] Skipped {quality} extraction due to error: {q_err}")
                continue

    except Exception as e:
        print(f"❌ [FilmyFly] Extraction Error: {e}")
    finally:
        await context.close()

    return final_links

# ==========================================
# 🌐 UI SERVER ENDPOINT
# ==========================================
@app.get("/")
async def serve_ui():
    return FileResponse("index.html")

# ==========================================
# 🧠 MEMORY CACHE SETUP
# ==========================================
SEARCH_CACHE = {}  # In-memory cache: { query_key: (results, timestamp) }
CACHE_EXPIRY = 3600 # Cache expiry time in seconds (1 hour) - can be adjusted based on needs

# ==========================================
#  API ENDPOINTS (STREAMING + CACHING)
# ==========================================
@app.get("/search")
async def api_search(q: str, limit: int = 4, sources: str = "9xflix,hdhub4u,filmyfly,filmyparda"):
    # Create a unique cache key based on query and settings
    query_key = f"{q.lower().strip()}_{limit}_{sources.lower().strip()}"
    print(f"\n⚡ [API] Search: '{q}' | Limit: {limit} | Sources: {sources}")

    async def result_generator():
        current_time = time.time()

        # 🟢 STEP 1: CHECK SMART CACHE
        if query_key in SEARCH_CACHE:
            cached_data, timestamp = SEARCH_CACHE[query_key]
            if current_time - timestamp < CACHE_EXPIRY:
                print("🚀 [CACHE HIT] Serving exact custom settings from memory!")
                yield f"data: {json.dumps({'results': cached_data})}\n\n"
                yield "data: [DONE]\n\n"
                return
            else:
                print("♻️ [CACHE EXPIRED] Deleting old custom data...")
                del SEARCH_CACHE[query_key]

        # 🔴 STEP 2: DYNAMIC TASK ROUTING
        print("🔍 [CACHE MISS] Booting up selected scraping engines...")
        tasks = []
        active_sources = [s.strip().lower() for s in sources.split(',')]

        # Note: The order of these if-blocks determines the priority of sources in the streaming results
        if "9xflix" in active_sources:
            tasks.append(asyncio.create_task(search_9xflix(q, limit)))
        if "hdhub4u" in active_sources:
            tasks.append(asyncio.create_task(search_hdhub(q, limit)))
        if "filmyfly" in active_sources:
            tasks.append(asyncio.create_task(search_filmyfly(q, limit)))
        if "filmyparda" in active_sources:
            tasks.append(asyncio.create_task(search_filmyparda(q, limit)))

        # if no valid sources are selected, return immediately
        if not tasks:
            print("⚠️ No valid sources selected!")
            yield "data: [DONE]\n\n"
            return

        all_fetched_results = []

        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                if result:
                    for res in result:
                        res["id"] = uuid.uuid4().hex[:8]

                    all_fetched_results.extend(result)
                    yield f"data: {json.dumps({'results': result})}\n\n"
            except Exception as e:
                print(f"❌ [API] Error in a background search task: {e}")

        # 🟢 STEP 3: SAVE TO CACHE
        if all_fetched_results:
            SEARCH_CACHE[query_key] = (all_fetched_results, current_time)
            print(f"💾 [CACHE SAVED] Custom query '{query_key}' saved in memory.")

        yield "data: [DONE]\n\n"

    return StreamingResponse(result_generator(), media_type="text/event-stream")

# ==========================================
# DEEP EXTRACTION ENDPOINT
# ==========================================

@app.post("/extract")
async def api_extract(req: ExtractRequest):
    print(f"\n⚡ [API] Deep Extraction requested for {req.source} -> {req.url} [Mode: {req.mode}]")

    try:
        source_name = req.source.lower()

        # Safe fallback just in case mode is None
        current_mode = req.mode if req.mode else "packs"

        if source_name == "9xflix":
            # only 9xFlix has a single extraction mode, so we ignore the mode parameter for it
            links = await extract_9xflix(req.url)

        elif source_name == "hdhub4u":
            # HDHub4u has multiple link types (packs vs episodes)
            links = await extract_hdhub(req.url, fetch_mode=current_mode)

        elif source_name == "filmyfly":
            links = await extract_filmyfly(req.url)

        elif source_name == "filmyparda":
            links = await extract_filmyparda(req.url)

        else:
            raise HTTPException(status_code=400, detail="Unknown source")

        return {"links": links}

    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return {"links": None}

# ==========================================
# RUN SERVER
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)