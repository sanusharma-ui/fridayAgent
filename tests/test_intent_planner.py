import json
import unittest
from unittest.mock import Mock

from backend.services.agent import DesktopAgent
from backend.services.commands import CommandRouter


def plan(tool, argument):
    return json.dumps({"type": "tools", "calls": [{"tool": tool, "argument": argument}]})


class NaturalIntentTests(unittest.TestCase):
    def setUp(self):
        self.ai = Mock()
        self.opened = []
        self.launched = []
        self.router = CommandRouter(self.ai, open_url=lambda url: self.opened.append(url) or True,
                                    launch=self.launched.append)
        self.agent = DesktopAgent(self.ai, self.router)

    def test_implied_app_request_uses_semantic_check(self):
        self.ai.ask.side_effect = [plan("open", "calculator"), '{"approved":true}']
        self.assertIn("Opening calculator", self.agent.handle("I need the app for doing sums"))
        self.assertEqual(self.launched, ["calc.exe"])

    def test_translated_search_does_not_require_literal_substring(self):
        self.ai.ask.side_effect = [plan("search_web", "lunar eclipse explanation"), '{"approved":true}']
        self.agent.handle("chandra grahan ke baare mein internet par dekho")
        self.assertIn("lunar+eclipse+explanation", self.opened[0])

    def test_semantic_rejection_or_provider_error_performs_no_action(self):
        for answer in ('{"approved":false}', '{"approved":"true"}', 'Friday is unavailable: timeout', 'not json'):
            self.ai.ask.side_effect = [plan("open", "calculator"), answer]
            self.assertIn("couldn't verify", self.agent.handle("I need some help"))
        self.assertFalse(self.launched)

    def test_clarification_completes_request_in_same_session(self):
        self.ai.ask.side_effect = [json.dumps({"type": "clarify", "message": "Which app?"}),
                                   plan("open", "calculator"), '{"approved":true}']
        self.assertEqual(self.agent.handle("Bring up an app for me"), "Which app?")
        self.agent.handle("calculator")
        self.assertEqual(self.launched, ["calc.exe"])
        self.assertIn("Previous user request", self.ai.ask.call_args_list[1].args[0])

    def test_clarification_does_not_cross_telegram_sessions(self):
        self.ai.ask.side_effect = [json.dumps({"type": "clarify", "message": "Which app?"}),
                                   '{"type":"chat"}', "Calculator is an app."]
        self.agent.handle("Bring up an app for me", mail_context="telegram:1")
        self.agent.handle("calculator", mail_context="telegram:2")
        self.assertNotIn("Previous user request", self.ai.ask.call_args_list[1].args[0])
        self.assertFalse(self.launched)

    def test_expired_context_is_not_reused(self):
        self.agent.clarifications["desktop"] = dict(request="open something", question="Which app?", expires=0)
        self.ai.ask.side_effect = ['{"type":"chat"}', "An answer."]
        self.agent.handle("calculator")
        self.assertNotIn("Previous user request", self.ai.ask.call_args_list[0].args[0])

    def test_browser_paraphrase_and_invalid_enum(self):
        browser = Mock()
        browser.page_context.return_value = "TITLE: Example"
        browser.control.return_value = "Went back."
        agent = DesktopAgent(self.ai, CommandRouter(self.ai, browser=browser))
        self.ai.ask.side_effect = [plan("browser_control", "back"), '{"approved":true}']
        self.assertEqual(agent.handle("Take me to the page I was on earlier"), "Went back.")
        self.ai.ask.side_effect = [plan("browser_control", "delete_everything")]
        self.assertIn("couldn't verify", agent.handle("Do something with the page"))
        browser.control.assert_called_once_with("back")

    def test_invented_browser_ref_never_gets_semantic_override(self):
        browser = Mock()
        browser.page_context.return_value = "[e1] button name='Continue'"
        agent = DesktopAgent(self.ai, CommandRouter(self.ai, browser=browser))
        self.ai.ask.side_effect = [plan("browser_click", "e99")]
        self.assertIn("couldn't verify", agent.handle("Press the continue button"))
        browser.click_element.assert_not_called()

    def test_general_planner_hands_off_mail_without_sending(self):
        self.agent.gmail._semantic = Mock(return_value="Email preview (not sent)")
        self.ai.ask.return_value = '{"type":"mail"}'
        self.assertIn("not sent", self.agent.handle("Ask Alex whether tomorrow works for him"))
        self.agent.gmail._semantic.assert_called_once_with("Ask Alex whether tomorrow works for him")

    def test_open_gmail_still_opens_site_without_ai(self):
        self.assertIn("Opening", self.agent.handle("open gmail"))
        self.ai.ask.assert_not_called()
        self.assertEqual(self.opened, ["https://mail.google.com"])

    def test_complete_plan_is_validated_before_first_action(self):
        self.ai.ask.side_effect = [json.dumps({"type": "tools", "calls": [
            {"tool": "open", "argument": "youtube"},
            {"tool": "open", "argument": "invented-site.com"}]}), '{"approved":false}']
        self.agent.handle("Take me to youtube and then something useful")
        self.assertFalse(self.opened)

    def test_form_value_stays_redacted_after_pending_clarification(self):
        browser = Mock()
        browser.page_context.return_value = "[e1] input type=text name='message'"
        browser.fill_element.return_value = "Filled."
        agent = DesktopAgent(self.ai, CommandRouter(self.ai, browser=browser))
        import time
        agent.clarifications["desktop"] = dict(request="open something", question="Which app?", expires=time.monotonic() + 300)
        self.ai.ask.return_value = plan("browser_fill", "e1")
        self.assertEqual(agent.handle("write private-value into the message field"), "Filled.")
        self.assertNotIn("private-value", self.ai.ask.call_args.args[0])
        browser.fill_element.assert_called_once_with("e1", "private-value")


if __name__ == "__main__":
    unittest.main()
