import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from services.agent import DesktopAgent
from services.browser import BrowserController, BrowserError, ChromeSession, site_for_url
from services.browser_commands import parse_browser_request
from services.commands import CommandRouter
from services.friday_service import FridayService


class BrowserTests(unittest.TestCase):
    def test_numbered_play_commands_execute_without_ai(self):
        browser = MagicMock()
        ai = MagicMock()
        agent = DesktopAgent(ai, CommandRouter(ai, browser=browser))
        for request in ["play 2", "play two", "play the second video", "play result 2", "play the second result", "play search result 2"]:
            agent.handle(request)
            browser.play_result.assert_called_with(2)
        self.assertEqual(browser.play_result.call_count, 6)
        ai.ask.assert_not_called()
        self.assertIsNone(parse_browser_request("don't play 2"))

    def test_numbered_play_checks_current_page_and_confirms_playback(self):
        session = self.session("https://www.youtube.com/results?search_query=piano")
        links = session.page.locator.return_value
        links.count.return_value = 3
        links.nth.return_value.get_attribute.return_value = "/watch?v=second"
        links.first.evaluate.return_value = True
        self.assertEqual(session.play_result(2), "Playing YouTube search result 2.")
        links.nth.assert_called_once_with(1)
        self.assertIn("await video.play()", links.first.evaluate.call_args.args[0])
        with self.assertRaisesRegex(BrowserError, "search results"):
            session.play_result(2)

    def test_plain_play_on_search_asks_for_number(self):
        session = self.session("https://www.youtube.com/results?search_query=piano")
        with self.assertRaisesRegex(BrowserError, "play 2"):
            session.control("play")
        session.page.locator.assert_not_called()

    def test_playback_failure_does_not_claim_playing(self):
        session = self.session("https://www.youtube.com/results?search_query=piano")
        links = session.page.locator.return_value
        links.count.return_value = 2
        links.nth.return_value.get_attribute.return_value = "/watch?v=second"
        links.first.evaluate.side_effect = RuntimeError("autoplay blocked")
        with self.assertRaisesRegex(BrowserError, "Opened result 2, but playback was not confirmed"):
            session.play_result(2)

    def session(self, url="https://www.youtube.com"):
        session = ChromeSession()
        session.browser = MagicMock()
        session.context = MagicMock()
        session.page = MagicMock()
        session.page.is_closed.return_value = False
        session.page.url = url
        session.context.pages = [session.page]
        session.page.goto.side_effect = lambda url, **kw: setattr(session.page, "url", url)
        return session

    def test_contextual_agent_sequence_without_ai(self):
        session = self.session()
        ai = MagicMock()
        router = CommandRouter(ai, browser=session)
        agent = DesktopAgent(ai, router)
        agent.handle("Can you open YouTube for me?")
        self.assertIn("YouTube", agent.handle("Search for piano music"))
        self.assertIn("search_query=piano+music", session.page.url)
        agent.handle("Scroll down")
        self.assertEqual(session.page.evaluate.call_args.args[1], "scroll_down")
        agent.handle("Go back")
        session.page.go_back.assert_called_once()
        ai.ask.assert_not_called()

    def test_ai_receives_fresh_page_context_for_element_click(self):
        browser = MagicMock()
        browser.page_context.return_value = (
            "TITLE: Example\n[e1] button, text='Continue'\n"
        )
        browser.click_element.return_value = "Clicked."
        ai = MagicMock()
        ai.ask.return_value = json.dumps({
            "type": "tools",
            "calls": [{"tool": "browser_click", "argument": "e1"}],
        })
        agent = DesktopAgent(ai, CommandRouter(ai, browser=browser))
        result = agent.handle("click the Continue button")
        self.assertEqual(result, "Clicked.")
        browser.page_context.assert_called_once()
        browser.click_element.assert_called_once_with("e1")
        self.assertIn("CURRENT PAGE CONTEXT", ai.ask.call_args.args[0])

    def test_element_click_requires_current_context_reference(self):
        browser = MagicMock()
        browser.page_context.return_value = "TITLE: Example\n[e2] link, text='Other'\n"
        ai = MagicMock()
        ai.ask.return_value = json.dumps({
            "type": "tools",
            "calls": [{"tool": "browser_click", "argument": "e1"}],
        })
        agent = DesktopAgent(ai, CommandRouter(ai, browser=browser))
        result = agent.handle("click the Continue button")
        self.assertIn("couldn't verify", result)
        browser.click_element.assert_not_called()

    def test_actual_url_determines_search_site(self):
        session = self.session("https://www.bing.com/search?q=test")
        session.search("new query")
        self.assertIn("bing.com/search?q=new+query", session.page.url)
        session.page.url = "https://example.com"
        with self.assertRaisesRegex(BrowserError, "not connected"):
            session.search("something")
        self.assertIsNone(site_for_url("https://youtube.com.evil.example"))

    def test_no_history_and_scroll_edge_are_not_success(self):
        session = self.session()
        session.page.go_back.return_value = None
        self.assertIn("no page", session.control("back"))
        session.page.evaluate.return_value = False
        self.assertIn("already at that edge", session.control("scroll_up"))

    def test_tabs_validate_indices_and_recover_closed_page(self):
        session = self.session()
        first = session.page
        second = MagicMock()
        second.is_closed.return_value = False
        second.title.return_value = "Second"
        session.context.pages = [first, second]
        with self.assertRaises(BrowserError):
            session.switch_tab(0)
        session.switch_tab(2)
        self.assertIs(session.page, second)
        second.is_closed.return_value = True
        session.context.pages = [first]
        self.assertIs(session._active_page(), first)

    def test_result_validation_does_not_navigate_invalid_links(self):
        session = self.session("https://www.youtube.com/results?search_query=piano")
        links = session.page.locator.return_value
        links.count.return_value = 2
        links.nth.return_value.get_attribute.return_value = "javascript:alert(1)"
        with self.assertRaises(BrowserError):
            session.open_result(1)
        with self.assertRaises(BrowserError):
            session.open_result(3)
        session.page.goto.assert_not_called()
        links.nth.return_value.get_attribute.return_value = "/watch?v=example"
        session.open_result(1)
        self.assertEqual(session.page.url, "https://www.youtube.com/watch?v=example")

    def test_browser_actor_owns_all_calls_and_cleanup_on_one_thread(self):
        threads = []
        class Session:
            def __init__(self):
                threads.append(threading.get_ident())
            def perform(self, op, arg):
                threads.append(threading.get_ident())
                return arg
            def close(self):
                threads.append(threading.get_ident())
        controller = BrowserController(session_factory=Session)
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                self.assertEqual(list(pool.map(controller.search, ["a", "b", "c"])), ["a", "b", "c"])
        finally:
            controller.close()
        self.assertEqual(len(threads), 5)
        self.assertEqual(len(set(threads)), 1)
        self.assertNotEqual(threads[0], threading.get_ident())
        with self.assertRaises(BrowserError):
            controller.search("later")

    def test_actor_factory_failure_is_reported_and_shutdown_completes(self):
        controller = BrowserController(session_factory=MagicMock(side_effect=BrowserError("startup failed")))
        try:
            with self.assertRaisesRegex(BrowserError, "startup failed"):
                controller.control("new_tab")
        finally:
            controller.close()

    def test_direct_english_parser_does_not_execute_questions_or_negation(self):
        for request in ["don't go back", "how do I scroll down?", "explain how to close tab"]:
            self.assertIsNone(parse_browser_request(request))
        self.assertEqual(parse_browser_request("Could you scroll down for me?"), ("browser_control", "scroll_down"))
        self.assertEqual(parse_browser_request("Search for moons on Google"), ("search_web", "moons"))
        self.assertEqual(parse_browser_request("Open the second result"), ("browser_result", "2"))
        for request, number in [
            ("click 2", "2"),
            ("click the 2nd link", "2"),
            ("click result 3", "3"),
            ("click the second result", "2"),
        ]:
            self.assertEqual(parse_browser_request(request), ("browser_result", number))
        self.assertEqual(parse_browser_request("Open Chrome"), ("browser_control", "new_tab"))

    def test_bad_model_direction_prevents_entire_plan(self):
        ai = MagicMock()
        ai.ask.return_value = json.dumps({"type": "tools", "calls": [
            {"tool": "open", "argument": "youtube"},
            {"tool": "browser_control", "argument": "scroll_down"}]})
        browser = MagicMock()
        agent = DesktopAgent(ai, CommandRouter(ai, browser=browser))
        result = agent.handle("open youtube and scroll up a little")
        self.assertIn("couldn't verify", result)
        browser.open_url.assert_not_called()
        browser.control.assert_not_called()

    def test_browser_error_is_shown_without_claiming_success(self):
        browser = MagicMock()
        browser.open_url.side_effect = BrowserError("Install Playwright")
        agent = DesktopAgent(MagicMock(), CommandRouter(MagicMock(), browser=browser))
        self.assertEqual(agent.handle("open youtube"), "Browser: Install Playwright")

    def test_english_instruction_preserves_api_contract(self):
        with patch("services.friday_service.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"response": "Hello"}
            service = FridayService("https://example.invalid", "test-key")
            self.assertEqual(service.ask("Answer my question"), "Hello")
            kwargs = post.call_args.kwargs
            self.assertTrue(kwargs["json"]["message"].startswith("Use English"))
            self.assertEqual(kwargs["headers"]["x-api-key"], "test-key")
            post.reset_mock()
            self.assertIn("too long", service.ask("x" * 4000))
            post.assert_not_called()
