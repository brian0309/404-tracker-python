import asyncio
import configparser
import threading
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup


class Scanner404:
    def __init__(
        self,
        base_url: str,
        config: configparser.ConfigParser,
        update_queue,
        stop_event: threading.Event,
        pause_event: threading.Event,
        crawl_subpages: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = config.getint("scanner", "timeout", fallback=10)
        self.user_agent = config.get("scanner", "user_agent", fallback="Mozilla/5.0")
        self.headers = {"User-Agent": self.user_agent}
        self.update_queue = update_queue
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.crawl_subpages = crawl_subpages

        self.visited = set()
        self.queued = set()
        self.visited_lock = asyncio.Lock()
        self.url_queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(50)

        self.url_queue.put_nowait((self.base_url, 0, True))
        self.queued.add(self.base_url)
        self.update_queue.put(("pending", self.base_url, "Seed"))

        self.session = None

    def is_internal(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                enable_cleanup_closed=True,
                force_close=False,
            )
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers,
            )
        return self.session

    async def fetch_head(self, url: str):
        if self.stop_event.is_set():
            return None, None, ""

        try:
            session = await self._get_session()
            async with self.semaphore:
                async with session.head(url, allow_redirects=True, ssl=False) as response:
                    return response.status, None, ""
        except Exception:
            return None, None, ""

    async def fetch_get(self, url: str):
        if self.stop_event.is_set():
            return None, None, ""

        try:
            session = await self._get_session()
            async with self.semaphore:
                async with session.get(url, allow_redirects=True, ssl=False) as response:
                    text = await response.text()
                    title = self.extract_title_fast(text)
                    return response.status, text, title
        except Exception:
            return None, None, ""

    @staticmethod
    def extract_title_fast(html: str) -> str:
        html_lower = html.lower()
        title_start = html_lower.find("<title>")
        if title_start == -1:
            title_start = html_lower.find("<title ")

        if title_start == -1:
            return ""

        title_end = html_lower.find("</title>", title_start)
        if title_end == -1:
            return ""

        actual_start = title_start + len("<title>")
        if html[title_start : title_start + 7].lower() != "<title>":
            tag_end = html.find(">", title_start)
            if tag_end != -1:
                actual_start = tag_end + 1

        title = html[actual_start:title_end].strip()
        title = (
            title.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
        )
        return title[:200]

    @staticmethod
    def extract_links(html: str, page_url: str) -> set[str]:
        links = set()
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all("a", href=True):
            href = tag["href"].split("#")[0].split("?")[0]
            full = urljoin(page_url, href)
            if full.startswith(("http://", "https://")):
                links.add(full)

        return links

    async def process_url(self, url: str, depth: int, expand_links: bool):
        if self.stop_event.is_set():
            return

        async with self.visited_lock:
            if url in self.visited:
                return
            self.visited.add(url)

        while not self.pause_event.is_set() and not self.stop_event.is_set():
            await asyncio.sleep(0.1)

        if self.stop_event.is_set():
            return

        head_status, _, _ = await self.fetch_head(url)
        body = None
        title = ""

        if head_status is None:
            status, body, title = await self.fetch_get(url)
            if status is None:
                self.update_queue.put(("row", url, "ERR", "Connection failed"))
                return
            head_status = status

        if head_status == 200:
            if body is None:
                status, body, title = await self.fetch_get(url)
            else:
                status = head_status

            status_str = str(status) if status else "ERR"
            self.update_queue.put(("row", url, status_str, title))

            if expand_links and status == 200 and body:
                for link in self.extract_links(body, url):
                    is_internal_link = self.is_internal(link)
                    child_expand_links = is_internal_link and self.crawl_subpages

                    async with self.visited_lock:
                        if link not in self.queued and link not in self.visited:
                            self.queued.add(link)
                            self.update_queue.put(("pending", link, url))
                            await self.url_queue.put((link, depth + 1, child_expand_links))
        else:
            status_str = str(head_status)
            self.update_queue.put(("row", url, status_str, ""))

    async def worker(self):
        while not self.stop_event.is_set():
            try:
                queue_item = await asyncio.wait_for(self.url_queue.get(), timeout=0.5)

                if isinstance(queue_item, tuple):
                    if len(queue_item) == 3:
                        url, depth, expand_links = queue_item
                    elif len(queue_item) == 2:
                        url, depth = queue_item
                        expand_links = self.crawl_subpages
                    else:
                        url, depth, expand_links = queue_item[0], 0, self.crawl_subpages
                else:
                    url, depth, expand_links = queue_item, 0, self.crawl_subpages

                try:
                    await self.process_url(url, depth, expand_links)
                except Exception as err:
                    self.update_queue.put(("row", url, "ERR", f"Processing error: {err}"))
                finally:
                    self.url_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

    async def scan(self, num_workers: int):
        workers = [asyncio.create_task(self.worker()) for _ in range(num_workers)]

        queue_join_task = asyncio.create_task(self.url_queue.join())
        while not self.stop_event.is_set():
            done, _ = await asyncio.wait([queue_join_task], timeout=0.2)
            if done:
                break

        self.stop_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if self.session and not self.session.closed:
            await self.session.close()
