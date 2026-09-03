from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import capture  # noqa: E402
import runner  # noqa: E402
from agent_browser import AgentBrowserClient  # noqa: E402


class AgentBrowserAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_capture_uses_viewport_only_evidence(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(return_value={"snapshot": {"nodes": []}})

        await capture.capture_structured_snapshot(
            cdp,
            max_nodes=7000,
            max_text_chars=200000,
        )

        cdp.call.assert_awaited_once_with(
            "ChromiumRL.captureStructuredSnapshot",
            {
                "inViewportOnly": True,
                "maxNodes": 7000,
                "maxTextChars": 200000,
                "includeOffscreen": False,
            },
        )

    def test_runner_reexports_structured_client(self) -> None:
        self.assertIs(runner.AgentBrowserClient, AgentBrowserClient)

    def client(self) -> runner.AgentBrowserClient:
        return runner.AgentBrowserClient(
            "agent-browser",
            session="fixture",
            cdp_url="http://127.0.0.1:49335",
            timeout=5,
        )

    def test_session_name_is_short_and_task_specific(self) -> None:
        first = runner.agent_browser_session_name("task-" + "x" * 120, 1234)
        second = runner.agent_browser_session_name("task-" + "y" * 120, 1234)
        self.assertLess(len(first), 40)
        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("-1234"))

    def test_missing_layout_box_is_a_recoverable_action_error(self) -> None:
        error = runner.AgentBrowserError(
            ["click", "@e1"],
            "CDP error (DOM.getBoxModel): Could not compute box model.",
        )
        self.assertTrue(runner.is_recoverable_action_error(error))

    def test_action_validation_uses_agent_browser_refs(self) -> None:
        refs = frozenset({"e1", "e7"})
        self.assertEqual(
            runner.action_rejection_reason(
                {"action": "click", "id": "e7"},
                refs,
                [],
            ),
            "",
        )
        self.assertIn(
            "agent-browser snapshot",
            runner.action_rejection_reason(
                {"action": "click", "id": "123"},
                refs,
                [],
            ),
        )
        self.assertIn(
            "not English",
            runner.action_rejection_reason(
                {"action": "terminate", "status": "success"},
                refs,
                [],
                "de",
            ),
        )

    def test_english_locale_path_normalization_is_generic(self) -> None:
        self.assertEqual(
            runner.english_locale_path_url(
                "https://example.test/de-DE/games?category=best#top"
            ),
            "https://example.test/en-US/games?category=best#top",
        )
        self.assertEqual(
            runner.english_locale_path_url("https://example.test/en-GB/games"),
            "",
        )

    async def test_visible_english_language_link_is_a_generic_alternate(self) -> None:
        cdp = unittest.mock.Mock()
        cdp.call = AsyncMock(
            return_value={
                "result": {
                    "value": {
                        "url": "https://example.test/",
                        "language": "de",
                        "alternates": [
                            {
                                "language": "",
                                "label": "English",
                                "url": "https://example.test/set-language?lang=en",
                                "authoritative": False,
                            }
                        ],
                    }
                }
            }
        )

        state = await runner.page_language_state(cdp)

        self.assertEqual(
            state.english_alternate_url,
            "https://example.test/set-language?lang=en",
        )

    async def test_actions_map_to_official_cli_commands(self) -> None:
        client = self.client()
        client._invoke = AsyncMock(return_value={"success": True, "data": {}})

        await client.execute({"action": "click", "id": "@e7"})
        client._invoke.assert_awaited_once_with(["click", "@e7"])

        client._invoke.reset_mock()
        await client.execute({"action": "back"})
        client._invoke.assert_awaited_once_with(["back"])

        client._invoke.reset_mock()
        await client.execute({"action": "fill", "id": "e1", "text": "hello world"})
        client._invoke.assert_awaited_once_with(["fill", "@e1", "hello world"])

        client._invoke.reset_mock()
        scroll_result = await client.execute(
            {"action": "scroll", "id": "e7", "pixels": -640}
        )
        self.assertEqual(
            client._invoke.await_args_list,
            [
                unittest.mock.call(["hover", "@e7"]),
                unittest.mock.call(["scroll", "up", "640"]),
            ],
        )
        self.assertEqual(
            scroll_result["normalized_parameters"],
            {"pixels": -640},
        )
        self.assertTrue(scroll_result["hover_issued"])

        client._invoke.reset_mock()
        wait_result = await client.execute({"action": "wait", "seconds": 60})
        client._invoke.assert_awaited_once_with(["wait", "10000"])
        self.assertEqual(
            wait_result["normalized_parameters"],
            {"seconds": 10.0},
        )

    async def test_snapshot_preserves_text_and_ref_set(self) -> None:
        client = self.client()
        client._invoke = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "origin": "https://example.test",
                    "refs": {
                        "e1": {"role": "button", "name": "Continue"},
                        "e2": {"role": "textbox", "name": "Search"},
                    },
                    "snapshot": '- button "Continue" [ref=e1]\n- textbox "Search" [ref=e2]',
                },
            }
        )

        observation = await client.snapshot()
        self.assertEqual(observation.refs, frozenset({"e1", "e2"}))
        self.assertEqual(
            observation.targets,
            {
                "e1": {"role": "button", "name": "Continue"},
                "e2": {"role": "textbox", "name": "Search"},
            },
        )
        self.assertTrue(observation.text.endswith("\n"))
        self.assertIn("[ref=e1]", observation.text)
        self.assertEqual(observation.command, ("snapshot", "-c"))
        client._invoke.assert_awaited_once_with(["snapshot", "-c"])

        client._invoke.reset_mock()
        interactive = await client.snapshot(interactive=True)
        self.assertEqual(interactive.command, ("snapshot", "-i"))
        client._invoke.assert_awaited_once_with(["snapshot", "-i"])

    def test_ref_target_identity_comes_from_same_interactive_snapshot(self) -> None:
        bundle = runner.CaptureBundle(
            snapshot=dict(url="https://example.test"),
            snapshot_path=Path("dom.json"),
            model_text="",
            screenshot_path=Path("screenshot.png"),
            agent_browser_action_text='- button "Search" [ref=e29]\n',
            agent_browser_refs=frozenset({"e29"}),
            agent_browser_targets={
                "e29": {"role": "button", "name": "Search"}
            },
        )

        target = runner.agent_browser_target_identity(
            {"action": "click", "id": "e29"},
            bundle,
        )

        self.assertEqual(
            target,
            {"ref": "e29", "role": "button", "name": "Search"},
        )

    def test_ref_target_identity_recovers_missing_metadata_from_exact_ref_line(
        self,
    ) -> None:
        bundle = runner.CaptureBundle(
            snapshot=dict(url="https://example.test"),
            snapshot_path=Path("dom.json"),
            model_text="",
            screenshot_path=Path("screenshot.png"),
            agent_browser_action_text=(
                '      - LabelText "Beginner(1,277)" [ref=e220] clickable\n'
                '        - checkbox "Beginner(1,277)" [ref=e302]\n'
            ),
            agent_browser_refs=frozenset({"e220", "e302"}),
            agent_browser_targets={
                "e220": {"role": "LabelText", "name": ""},
                "e302": {"role": "checkbox", "name": "Beginner(1,277)"},
            },
        )

        target = runner.agent_browser_target_identity(
            {"action": "click", "id": "e220"},
            bundle,
        )

        self.assertEqual(
            target,
            {"ref": "e220", "role": "LabelText", "name": "Beginner(1,277)"},
        )

    async def test_non_transport_cdp_send_error_is_raised_immediately(self) -> None:
        cdp = runner.CDPClient("http://127.0.0.1:9222")
        cdp.ws = AsyncMock()
        cdp.ws.send_json.side_effect = RuntimeError("serialization failed")

        with self.assertRaisesRegex(RuntimeError, "serialization failed"):
            await cdp.call("Page.getFrameTree")

        self.assertEqual(cdp.pending, {})

    async def test_active_page_uses_official_tab_list(self) -> None:
        client = self.client()
        client._invoke = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "tabs": [
                        {
                            "active": False,
                            "tabId": "t1",
                            "title": "Catalog",
                            "type": "page",
                            "url": "https://example.test/games",
                        },
                        {
                            "active": True,
                            "tabId": "t2",
                            "title": "Product",
                            "type": "page",
                            "url": "https://example.test/product/1",
                        },
                    ]
                },
            }
        )

        page = await client.active_page()

        self.assertEqual(
            page,
            runner.AgentBrowserPage(
                tab_id="t2",
                url="https://example.test/product/1",
                title="Product",
            ),
        )
        client._invoke.assert_awaited_once_with(["tab", "list"])

    async def test_connect_creates_fresh_tab_and_closes_every_old_page(self) -> None:
        class FakeResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def json(self):
                return {"webSocketDebuggerUrl": "ws://localhost/devtools/browser/test"}

        class FakeWebSocket:
            async def close(self):
                return None

        class FakeHTTP:
            def get(self, *_args, **_kwargs):
                return FakeResponse()

            async def ws_connect(self, *_args, **_kwargs):
                return FakeWebSocket()

            async def close(self):
                return None

        cdp = runner.CDPClient("http://127.0.0.1:49335")
        cdp._read_messages = AsyncMock()
        old_pages = [
            {
                "targetId": "old-one",
                "type": "page",
                "title": "Old one",
                "url": "https://old-one.example/",
            },
            {
                "targetId": "old-two",
                "type": "page",
                "title": "Old two",
                "url": "https://old-two.example/",
            },
        ]
        calls: list[tuple[str, dict, bool]] = []
        target_reads = 0
        closed_targets: set[str] = set()

        async def fake_call(method, params=None, *, attached=True):
            nonlocal target_reads
            calls.append((method, params or {}, attached))
            if method == "Target.getTargets":
                target_reads += 1
                if target_reads == 1:
                    return {"targetInfos": old_pages}
                return {
                    "targetInfos": [
                        *[
                            page
                            for page in old_pages
                            if page["targetId"] not in closed_targets
                        ],
                        {
                            "targetId": "fresh",
                            "type": "page",
                            "title": "",
                            "url": "about:blank",
                        },
                    ]
                }
            if method == "Target.createTarget":
                return {"targetId": "fresh"}
            if method == "Target.closeTarget":
                closed_targets.add(params["targetId"])
                return {"success": True}
            if method == "Target.attachToTarget":
                return {"sessionId": "fresh-session"}
            return {}

        cdp.call = AsyncMock(side_effect=fake_call)
        with patch.object(
            runner.aiohttp,
            "ClientSession",
            return_value=FakeHTTP(),
        ):
            await cdp.connect()

        closed_ids = [
            params["targetId"]
            for method, params, attached in calls
            if method == "Target.closeTarget" and not attached
        ]
        self.assertEqual(closed_ids, ["old-one", "old-two"])
        self.assertEqual(cdp.target["targetId"], "fresh")
        self.assertTrue(cdp.connection_report["tab_cleanup"]["fresh_target_created"])
        self.assertEqual(cdp.connection_report["tab_cleanup"]["closed_count"], 2)
        self.assertIn(
            ("Target.activateTarget", {"targetId": "fresh"}, False),
            calls,
        )
        await cdp.close()

    async def test_recorder_reconnects_closed_cdp_to_active_agent_tab(self) -> None:
        active = runner.AgentBrowserPage(
            tab_id="t2",
            url="https://example.test/product/1",
            title="Product",
        )
        cdp = MagicMock()
        cdp.synchronize_target = AsyncMock(
            side_effect=runner.RunnerError("CDP websocket closed")
        )
        cdp.reconnect_active_page = AsyncMock(
            return_value={"transport_reconnected": True}
        )
        agent_browser = MagicMock()
        agent_browser.active_page = AsyncMock(return_value=active)

        report = await runner.synchronize_recorder_target(
            cdp, agent_browser, attempts=1
        )

        self.assertTrue(report["transport_reconnected"])
        cdp.reconnect_active_page.assert_awaited_once_with(active)

    async def test_cdp_capture_switches_to_agent_browser_active_tab(self) -> None:
        cdp = runner.CDPClient(
            "http://127.0.0.1:49335",
            browser_language="en-US",
            browser_accept_language="en-US,en;q=0.9",
        )
        cdp.target = {
            "targetId": "old-target",
            "type": "page",
            "title": "Catalog",
            "url": "https://example.test/games",
        }
        cdp.session_id = "old-session"
        cdp.connection_report = {"target_switches": []}
        calls: list[tuple[str, dict, bool]] = []

        async def fake_call(method, params=None, *, attached=True):
            calls.append((method, params or {}, attached))
            if method == "Target.getTargets":
                return {
                    "targetInfos": [
                        cdp.target,
                        {
                            "targetId": "new-target",
                            "type": "page",
                            "title": "Product",
                            "url": "https://example.test/product/1",
                        },
                    ]
                }
            if method == "Target.attachToTarget":
                return {"sessionId": "new-session"}
            return {}

        cdp.call = AsyncMock(side_effect=fake_call)
        report = await cdp.synchronize_target(
            runner.AgentBrowserPage(
                tab_id="t2",
                url="https://example.test/product/1",
                title="Product",
            )
        )

        self.assertTrue(report["switched"])
        self.assertEqual(cdp.target["targetId"], "new-target")
        self.assertEqual(cdp.session_id, "new-session")
        self.assertIn(
            (
                "Target.detachFromTarget",
                {"sessionId": "old-session"},
                False,
            ),
            calls,
        )
        self.assertIn(
            (
                "Target.attachToTarget",
                {"targetId": "new-target", "flatten": True},
                False,
            ),
            calls,
        )
        self.assertIn(("ChromiumRL.enable", {}, True), calls)
        self.assertEqual(len(cdp.connection_report["target_switches"]), 1)

    async def test_cdp_capture_rejects_ambiguous_active_tab_match(self) -> None:
        cdp = runner.CDPClient("http://127.0.0.1:49335")
        cdp.target = {
            "targetId": "old-target",
            "type": "page",
            "title": "Duplicate",
            "url": "https://example.test/same",
        }
        cdp.session_id = "old-session"
        cdp.call = AsyncMock(
            return_value={
                "targetInfos": [
                    cdp.target,
                    {
                        "targetId": "other-target",
                        "type": "page",
                        "title": "Duplicate",
                        "url": "https://example.test/same",
                    },
                ]
            }
        )

        with self.assertRaisesRegex(runner.RunnerError, "multiple CDP page targets"):
            await cdp.synchronize_target(
                runner.AgentBrowserPage(
                    tab_id="t2",
                    url="https://example.test/same",
                    title="Duplicate",
                )
            )

    async def test_observation_retry_preserves_successful_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bundle = runner.CaptureBundle(
                snapshot={},
                snapshot_path=directory / "dom.json",
                model_text="",
                screenshot_path=directory / "screenshot.png",
            )
            client = self.client()
            client.snapshot = AsyncMock(
                side_effect=[
                    runner.AgentBrowserError(["snapshot", "-c"], "transient"),
                    runner.AgentBrowserObservation(
                        text='- button "Continue" [ref=e1]\n',
                        refs=frozenset({"e1"}),
                        origin="https://example.test",
                        command=("snapshot", "-c"),
                    ),
                    runner.AgentBrowserObservation(
                        text='- button "Continue" [ref=e7]\n',
                        refs=frozenset({"e7"}),
                        origin="https://example.test",
                        command=("snapshot", "-i"),
                        targets={
                            "e7": {"role": "button", "name": "Continue"}
                        },
                    ),
                ]
            )
            client.reconnect = AsyncMock()
            with patch.object(runner.asyncio, "sleep", new=AsyncMock()) as sleep:
                observed = await runner.attach_agent_browser_observation(
                    bundle,
                    client,
                    attempts=2,
                )

            self.assertEqual(client.snapshot.await_count, 3)
            client.reconnect.assert_awaited_once()
            sleep.assert_awaited_once()
            self.assertEqual(observed.agent_browser_refs, frozenset({"e7"}))
            self.assertEqual(
                observed.agent_browser_targets,
                {"e7": {"role": "button", "name": "Continue"}},
            )
            self.assertEqual(observed.agent_browser_snapshot_command, ("snapshot", "-c"))
            self.assertEqual(
                observed.agent_browser_action_snapshot_command,
                ("snapshot", "-i"),
            )
            self.assertEqual(
                (directory / "agent_browser.txt").read_text(encoding="utf-8"),
                '- button "Continue" [ref=e1]\n',
            )
            self.assertEqual(
                (directory / "agent_browser_actions.txt").read_text(encoding="utf-8"),
                '- button "Continue" [ref=e7]\n',
            )

    def test_failed_observation_is_materialized_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bundle = runner.CaptureBundle(
                snapshot={},
                snapshot_path=directory / "dom.json",
                model_text="",
                screenshot_path=directory / "screenshot.png",
            )
            observed = runner.attach_agent_browser_observation_error(
                bundle,
                runner.RunnerError("snapshot unavailable"),
            )

            self.assertFalse(observed.agent_browser_refs)
            self.assertEqual(observed.agent_browser_snapshot_command, ())
            self.assertIn(
                "snapshot unavailable",
                (directory / "agent_browser.txt").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "snapshot unavailable",
                (directory / "agent_browser_actions.txt").read_text(encoding="utf-8"),
            )

    def test_model_prompt_strips_non_actionable_chromiumrl_guidance(self) -> None:
        text = (
            "Use only ids from this observation. Scroll with a made-up tool.\n"
            "=== SCROLLABLE REGIONS ===\n"
            'Use: scroll("down", 1600, element_id=<id>).\n'
            "[19] page content — 1200x800\n"
            "Not currently clickable. To interact with these rows, scroll [19].\n"
            "Visible result text\n"
        )

        model_text = runner.chromiumrl_evidence_for_model(text)

        self.assertNotIn("Use only ids from this observation.", model_text)
        self.assertNotIn('Use: scroll("down"', model_text)
        self.assertNotIn("Not currently clickable.", model_text)
        self.assertNotIn("=== SCROLLABLE REGIONS ===", model_text)
        self.assertNotIn("page content", model_text)
        self.assertIn("Visible result text", model_text)

    def test_model_prompt_removes_complete_scroll_region_block_without_changing_stored_output(
        self,
    ) -> None:
        text = (
            "=== ADDITIONAL CAPTURED CONTENT ===\n"
            "Not currently clickable. To interact with these rows, scroll [7528] page content.\n"
            "Recorded offscreen evidence\n"
            "=== SCROLLABLE REGIONS ===\n"
            'Use: scroll("down", 1600, element_id=<id>) or scroll("up", 1600, element_id=<id>).\n'
            "[7528] page content — 1200x800\n"
            "[A1] Results pane (list) — 640x480\n"
            "[Promotion] Sponsored panel — 320x240\n"
            "[scrollable regions hidden: 4 more]\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            stored_path = Path(temp_dir) / "dom_model.txt"
            stored_path.write_text(text, encoding="utf-8")
            stored_before = stored_path.read_bytes()

            model_text = runner.chromiumrl_evidence_for_model(
                stored_path.read_text(encoding="utf-8")
            )

            self.assertEqual(stored_path.read_bytes(), stored_before)
        self.assertIn("=== ADDITIONAL CAPTURED CONTENT ===", model_text)
        self.assertIn("Recorded offscreen evidence", model_text)
        self.assertNotIn("To interact with these rows, scroll", model_text)
        self.assertNotIn("=== SCROLLABLE REGIONS ===", model_text)
        self.assertNotIn("[7528]", model_text)
        self.assertNotIn("[A1]", model_text)
        self.assertNotIn("[Promotion]", model_text)
        self.assertNotIn("scrollable regions hidden", model_text)

    def test_model_prompt_hides_non_executable_dom_ids_without_losing_values(self) -> None:
        text = (
            '[19] link "Tata Salt 1 Kg"\n'
            '  actions: [1175] button "Watch"; [335] link "4.5 stars"\n'
        )
        model_text = runner.chromiumrl_evidence_for_model(text)
        self.assertNotIn("[19]", model_text)
        self.assertNotIn("[1175]", model_text)
        self.assertNotIn("[335]", model_text)
        self.assertIn("Tata Salt 1 Kg", model_text)
        self.assertIn("4.5 stars", model_text)

    def test_browser_decision_excludes_model_only_memory_and_thought(self) -> None:
        decision = {
            "action": "click",
            "id": "e7",
            "thought": "Click the visible Continue button.",
            "memory": "verified fact",
        }
        self.assertEqual(
            runner.browser_decision(decision),
            {"action": "click", "id": "e7"},
        )

    def test_writable_control_verification_uses_target_ref_line(self) -> None:
        before = runner.CaptureBundle(
            snapshot={},
            snapshot_path=Path("before-dom.json"),
            model_text="",
            screenshot_path=Path("before-screenshot.png"),
            agent_browser_text='- textbox "Search" [ref=e9]\n',
        )
        after = runner.CaptureBundle(
            snapshot={},
            snapshot_path=Path("after-dom.json"),
            model_text="",
            screenshot_path=Path("after-screenshot.png"),
            agent_browser_text=(
                '- link "Different element" [ref=e9]\n'
                '- textbox "Search" [ref=e7]: Berlin Hauptbahnhof\n'
            ),
        )
        verified = runner.verify_agent_browser_action(
            {"action": "fill", "id": "e9", "text": "Berlin Hauptbahnhof"},
            before,
            after,
        )
        self.assertEqual(verified["status"], "verified")
        mismatch = runner.verify_agent_browser_action(
            {"action": "fill", "id": "e9", "text": "Munich"},
            before,
            after,
        )
        self.assertEqual(mismatch["status"], "mismatch")

    def test_recent_stalled_strategy_is_rejected(self) -> None:
        stalled = {"made_progress": False}
        recent = [
            {"action": {"action": "click", "id": "e23"}, "progress": stalled},
            {"action": {"action": "click", "id": "e24"}, "progress": stalled},
        ]
        self.assertIn(
            "stalled strategy",
            runner.action_rejection_reason(
                {"action": "click", "id": "e23"},
                frozenset({"e23", "e24"}),
                recent,
            ),
        )

    def test_snapshot_local_ref_can_be_reused_on_a_different_page(self) -> None:
        recent = [
            {
                "action": {"action": "click", "id": "e24"},
                "action_context": {
                    "document_url": "https://example.test/archive/page/2",
                    "control_signature": 'link "next"',
                },
                "progress": {"made_progress": False},
            }
        ]
        self.assertEqual(
            runner.action_rejection_reason(
                {"action": "click", "id": "e24"},
                frozenset({"e24"}),
                recent,
                action_context={
                    "document_url": "https://example.test/archive/page/3",
                    "control_signature": 'link "next"',
                    "ref": "e24",
                    "role": "link",
                    "name": "Next",
                },
            ),
            "",
        )

    def test_no_progress_duplicate_on_same_observation_is_rejected(self) -> None:
        context = {
            "document_url": "https://example.test/archive/page/2",
            "control_signature": 'button "continue"',
            "ref": "e7",
            "role": "button",
            "name": "Continue",
        }
        recent = [
            {
                "action": {"action": "click", "id": "e7"},
                "action_context": context,
                "progress": {"made_progress": False},
            }
        ]
        self.assertIn(
            "no observable progress",
            runner.action_rejection_reason(
                {"action": "click", "id": "e7"},
                frozenset({"e7"}),
                recent,
                action_context=context,
            ),
        )

    def test_progressing_two_action_pattern_is_not_rejected(self) -> None:
        progressed = {"made_progress": True}
        recent = [
            {"action": {"action": "scroll", "pixels": 800}, "progress": progressed},
            {"action": {"action": "scroll", "pixels": -800}, "progress": progressed},
            {"action": {"action": "scroll", "pixels": 800}, "progress": progressed},
        ]
        self.assertEqual(
            runner.action_rejection_reason(
                {"action": "scroll", "pixels": -800},
                frozenset(),
                recent,
            ),
            "",
        )

    def test_no_progress_two_action_cycle_is_rejected(self) -> None:
        stalled = {"made_progress": False}
        recent = [
            {"action": {"action": "scroll", "pixels": 800}, "progress": stalled},
            {"action": {"action": "scroll", "pixels": -800}, "progress": stalled},
            {"action": {"action": "scroll", "pixels": 800}, "progress": stalled},
        ]
        self.assertIn(
            "two-action cycle",
            runner.action_rejection_reason(
                {"action": "scroll", "pixels": -800},
                frozenset(),
                recent,
            ),
        )

    def test_successful_termination_requires_a_successful_recorded_action(self) -> None:
        decision = {"action": "terminate", "status": "success"}
        self.assertIn(
            "at least one confirmed browser action",
            runner.action_rejection_reason(decision, frozenset(), []),
        )
        failed = [
            {
                "action": {"action": "click", "id": "e1"},
                "progress": {"made_progress": False},
                "action_succeeded": False,
            }
        ]
        self.assertIn(
            "at least one confirmed browser action",
            runner.action_rejection_reason(decision, frozenset(), failed),
        )
        successful = [
            {"action": {"action": "scroll"}, "progress": {}, "action_succeeded": True}
        ]
        self.assertEqual(
            runner.action_rejection_reason(decision, frozenset(), successful), ""
        )



if __name__ == "__main__":
    unittest.main()
