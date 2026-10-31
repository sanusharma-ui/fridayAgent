"""Stateful Chrome control. Playwright objects stay on one dedicated thread."""

from concurrent.futures import Future
from queue import Queue
import threading
from urllib.parse import quote_plus, urljoin, urlparse


class BrowserError(RuntimeError):
    pass


def site_for_url(url):
    host = (urlparse(url).hostname or "").lower()
    if host == "youtube.com" or host.endswith(".youtube.com"):
        return "YouTube"
    if host in {"google.com", "www.google.com", "google.co.in", "www.google.co.in"}:
        return "Google"
    if host in {"bing.com", "www.bing.com"}:
        return "Bing"
    if host in {"duckduckgo.com", "www.duckduckgo.com"}:
        return "DuckDuckGo"
    return None


class ChromeSession:
    """An isolated, visible browser session, never the user's personal profile."""

    def __init__(self, channel="chrome"):
        self.channel = channel
        self.driver = None
        self.browser = None
        self.context = None
        self.page = None

    def _start(self):
        if self.browser and self.browser.is_connected():
            return
        self.close()
        if self.channel not in {"chrome", "msedge", "chromium"}:
            raise BrowserError("BROWSER_CHANNEL must be chrome, msedge, or chromium.")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise BrowserError("Chrome controls need Playwright. Run: python -m pip install -r requirements.txt, then restart the app.") from None
        try:
            self.driver = sync_playwright().start()
            options = {"headless": False, "timeout": 20000, "args": ["--start-maximized"]}
            if self.channel != "chromium":
                options["channel"] = self.channel
            self.browser = self.driver.chromium.launch(**options)
            self.context = self.browser.new_context(no_viewport=True, accept_downloads=False)
            self.context.set_default_timeout(10000)
            self.context.set_default_navigation_timeout(20000)
        except Exception:
            self.close()
            raise BrowserError("Could not start the controlled browser. Install Google Chrome, or configure BROWSER_CHANNEL. Close any blocked startup dialog and try again.") from None

    def _active_page(self):
        if not self.browser or not self.browser.is_connected() or not self.context:
            raise BrowserError("No controlled Chrome session is open. Ask me to open YouTube or a website first.")
        if not self.page or self.page.is_closed():
            pages = [page for page in self.context.pages if not page.is_closed()]
            if not pages:
                raise BrowserError("The controlled tab is closed. Ask me to open a website again.")
            self.page = pages[-1]
        self.page.bring_to_front()
        return self.page

    @staticmethod
    def _validate_url(url):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise BrowserError("Please provide a regular http or https website address.")

    def open_url(self, url):
        self._validate_url(url)
        self._start()
        if not self.page or self.page.is_closed():
            self.page = self.context.new_page()
        self.page.bring_to_front()
        self.page.goto(url, wait_until="domcontentloaded")
        return True

    def search(self, query):
        if not query.strip():
            raise BrowserError("What should I search for?")
        if not self.browser:
            site = "Google"
        else:
            page = self._active_page()
            site = site_for_url(page.url)
            if page.url == "about:blank":
                site = "Google"
        templates = {
            "YouTube": "https://www.youtube.com/results?search_query=",
            "Google": "https://www.google.com/search?q=",
            "Bing": "https://www.bing.com/search?q=",
            "DuckDuckGo": "https://duckduckgo.com/?q=",
        }
        if site not in templates:
            raise BrowserError("Search on this website is not connected. Specify 'search ... on YouTube' or 'search ... on Google'.")
        self.open_url(templates[site] + quote_plus(query))
        return f"Searching {site} for {query}."

    def control(self, action):
        if action == "new_tab":
            self._start()
            self.page = self.context.new_page()
            self.page.bring_to_front()
            return "Opened a new controlled Chrome tab."
        page = self._active_page()
        if action in {"back", "forward"}:
            before = page.url
            result = page.go_back(wait_until="domcontentloaded") if action == "back" else page.go_forward(wait_until="domcontentloaded")
            if result is None and page.url == before:
                return f"There is no page to go {action} to in this tab."
            return f"Moved {action} in the current Chrome tab."
        if action == "refresh":
            page.reload(wait_until="domcontentloaded")
            return "Refreshed the current Chrome tab."
        if action in {"scroll_up", "scroll_down", "top", "bottom"}:
            # Fixed code only: no model-generated JavaScript is evaluated.
            moved = page.evaluate("""action => {
                const before = window.scrollY;
                const amount = Math.round(window.innerHeight * 0.8);
                if (action === 'top') window.scrollTo({top: 0, behavior: 'instant'});
                else if (action === 'bottom') window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'});
                else window.scrollBy({top: action === 'scroll_up' ? -amount : amount, behavior: 'instant'});
                return window.scrollY !== before;
            }""", action)
            return (f"Scrolled the current Chrome page {action.replace('scroll_', '')}." if moved
                    else "The page is already at that edge or has no scrollable content.")
        if action == "tabs":
            return "Chrome tabs:\n" + "\n".join(
                f"{index}. {'[current] ' if tab == page else ''}{tab.title()[:100] or 'New tab'}"
                for index, tab in enumerate(self.context.pages, 1))
        if action == "close_tab":
            page.close()
            self.page = self.context.pages[-1] if self.context.pages else None
            if self.page:
                self.page.bring_to_front()
            return "Closed the current controlled Chrome tab."
        if action in {"play", "pause"}:
            if site_for_url(page.url) != "YouTube":
                raise BrowserError("Video play/pause is supported on the current YouTube tab.")
            if urlparse(page.url).path == "/results":
                raise BrowserError("You are on YouTube search results. Say 'play 1' or 'play 2' to choose a video.")
            videos = page.locator("video")
            try:
                videos.first.wait_for(state="attached", timeout=10000)
                playing = videos.first.evaluate("async video => { await video.play(); return !video.paused; }" if action == "play" else "video => { video.pause(); return video.paused; }")
            except Exception:
                raise BrowserError("The video could not start or pause. Check the player or consent dialog and try again.") from None
            if not playing:
                raise BrowserError("The player did not confirm the requested playback state. Please check the video.")
            return "Playing the current YouTube video." if action == "play" else "Paused the current YouTube video."
        raise BrowserError("That browser control is not supported.")

    def switch_tab(self, number):
        self._active_page()
        pages = self.context.pages
        if not 1 <= number <= len(pages):
            raise BrowserError(f"Choose a tab number from 1 to {len(pages)}.")
        self.page = pages[number - 1]
        self.page.bring_to_front()
        return f"Switched to Chrome tab {number}: {self.page.title()[:100] or 'New tab'}."

    def play_result(self, number):
        page = self._active_page()
        if site_for_url(page.url) != "YouTube" or urlparse(page.url).path != "/results":
            raise BrowserError("Numbered playback needs YouTube search results. Search on YouTube first, then say 'play 2'.")
        self.open_result(number)
        try:
            self.control("play")
        except BrowserError as exc:
            raise BrowserError(f"Opened result {number}, but playback was not confirmed. {exc}") from None
        return f"Playing YouTube search result {number}."

    def open_result(self, number):
        page = self._active_page()
        site = site_for_url(page.url)
        if site == "YouTube" and urlparse(page.url).path == "/results":
            links = page.locator("ytd-video-renderer a#video-title[href]")
        elif site == "Google" and urlparse(page.url).path == "/search":
            links = page.locator("a:has(h3)")
        else:
            raise BrowserError("Open a YouTube or Google search first, then say 'open result 1'.")
        try:
            links.first.wait_for(state="visible", timeout=10000)
        except Exception:
            raise BrowserError("Search results are not ready. Check the connection and close any consent dialog, then retry.") from None
        count = links.count()
        if not 1 <= number <= min(count, 20):
            raise BrowserError("That result is not available. Check that results have loaded and any consent dialog is closed.")
        link = links.nth(number - 1)
        href = link.get_attribute("href")
        if not href:
            raise BrowserError("That result does not have a website link.")
        url = urljoin(page.url, href)
        self._validate_url(url)
        if site == "YouTube" and (site_for_url(url) != "YouTube" or urlparse(url).path != "/watch"):
            raise BrowserError("That result is not a YouTube video link.")
        self.open_url(url)
        return f"Opened search result {number} in Chrome."

    def perform(self, operation, argument):
        try:
            if operation == "open":
                return self.open_url(argument)
            if operation == "search":
                return self.search(argument)
            if operation == "control":
                return self.control(argument)
            if operation == "switch_tab":
                return self.switch_tab(int(argument))
            if operation == "open_result":
                return self.open_result(int(argument))
            if operation == "play_result":
                return self.play_result(int(argument))
            raise BrowserError("Unsupported browser operation.")
        except BrowserError:
            raise
        except Exception:
            raise BrowserError("Chrome could not finish that action. Check the page, connection, or any browser dialog and try again.") from None

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        finally:
            if self.driver:
                try:
                    self.driver.stop()
                except Exception:
                    pass
            self.driver = self.browser = self.context = self.page = None


class BrowserController:
    def __init__(self, channel="chrome", session_factory=None):
        self._factory = session_factory or (lambda: ChromeSession(channel))
        self._queue = Queue()
        self._lock = threading.Lock()
        self._thread = None
        self._closed = False

    def _run(self):
        session = None
        try:
            while True:
                task = self._queue.get()
                if task is None:
                    break
                operation, argument, future = task
                if future.set_running_or_notify_cancel():
                    try:
                        if session is None:
                            session = self._factory()
                        future.set_result(session.perform(operation, argument))
                    except Exception as exc:
                        future.set_exception(exc)
        finally:
            if session is not None:
                session.close()

    def _call(self, operation, argument=""):
        future = Future()
        with self._lock:
            if self._closed:
                raise BrowserError("Browser controls have stopped. Restart the desktop app.")
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="neo-browser", daemon=True)
                self._thread.start()
            self._queue.put((operation, argument, future))
        return future.result()

    def open_url(self, url):
        return self._call("open", url)

    def search(self, query):
        return self._call("search", query)

    def control(self, action):
        return self._call("control", action)

    def switch_tab(self, number):
        return self._call("switch_tab", number)

    def open_result(self, number):
        return self._call("open_result", number)

    def play_result(self, number):
        return self._call("play_result", number)

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                if self._thread:
                    self._queue.put(None)
            thread = self._thread
        if thread:
            thread.join()
