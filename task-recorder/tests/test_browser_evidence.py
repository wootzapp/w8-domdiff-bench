"""Opt-in checks against an isolated browser, never against recorded evidence.

Run with EVIDENCE_TEST_CDP_URL pointing at a disposable browser. The fixtures
exercise generic capture/formatting cases; no website-specific rules are used.
"""

import os
import unittest

from capture import CDPClient


@unittest.skipUnless(os.environ.get("EVIDENCE_TEST_CDP_URL"), "isolated browser required")
class BrowserEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cdp = CDPClient(os.environ["EVIDENCE_TEST_CDP_URL"])
        await self.cdp.connect()
        await self.cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1000, "height": 720, "deviceScaleFactor": 1, "mobile": False,
        })

    async def asyncTearDown(self):
        await self.cdp.close()

    async def page(self, html):
        await self.cdp.call("Page.navigate", {"url": "about:blank"})
        frame = (await self.cdp.call("Page.getFrameTree"))["frameTree"]["frame"]["id"]
        await self.cdp.call("Page.setDocumentContent", {"frameId": frame, "html": html})
        await self.settle()

    async def settle(self):
        await self.cdp.call("Runtime.evaluate", {
            "expression": "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))",
            "awaitPromise": True,
        })

    async def capture(self, offscreen=False):
        response = await self.cdp.call("ChromiumRL.captureStructuredSnapshot", {
            "inViewportOnly": not offscreen, "includeOffscreen": offscreen,
            "maxNodes": 7000, "maxTextChars": 200000,
            "includeDiff": False, "updateBaseline": False,
        })
        snapshot = response["snapshot"]
        result = await self.cdp.call("ChromiumRL.getModelDOM", {"snapshot": snapshot})
        model = result["modelDOM"]
        text = "\n".join(line for section in model["sections"] for line in section["lines"])
        return snapshot, text

    @staticmethod
    def leaf_text(snapshot):
        return "\n".join(n.get("subtreeText", "") for n in snapshot["nodes"]
                         if {"name": "textScope", "value": "viewport"} in n["states"])

    async def test_long_text_tracks_vertical_scroll_without_offscreen_tail(self):
        lines = [f"record_{i:03d}: visible text with its exact value {i * 7}" for i in range(150)]
        await self.page('<pre style="font:16px/24px monospace; margin:0">' + "\n".join(lines) + '</pre>')
        before, model = await self.capture()
        text = self.leaf_text(before)
        self.assertGreater(len(text), 500)
        self.assertIn("record_020", text)
        self.assertNotIn("record_090", text)
        self.assertIn("record_020", model)
        await self.cdp.call("Runtime.evaluate", {"expression": "scrollTo(0, 1920)"})
        await self.settle()
        after, model = await self.capture()
        text = self.leaf_text(after)
        self.assertIn("record_085", text)
        self.assertNotIn("record_000", text)
        self.assertNotIn("record_149", text)
        self.assertIn("record_085", model)
        self.assertNotIn("record_000", model)

    async def test_horizontal_overflow_respects_clipping_and_scroll(self):
        await self.page('<pre id="text" style="width:200px;overflow:auto;font:16px monospace">'
                        + 'START_VISIBLE ' + 'x' * 1000 + ' END_VISIBLE</pre>')
        before, _ = await self.capture()
        self.assertIn("START_VISIBLE", self.leaf_text(before))
        self.assertNotIn("END_VISIBLE", self.leaf_text(before))
        await self.cdp.call("Runtime.evaluate", {
            "expression": "document.querySelector('#text').scrollLeft = 100000",
        })
        await self.settle()
        after, _ = await self.capture()
        self.assertIn("END_VISIBLE", self.leaf_text(after))
        self.assertNotIn("START_VISIBLE", self.leaf_text(after))

    async def test_nonviewport_capture_keeps_existing_prefix_contract(self):
        await self.page('<pre>' + 'word ' * 400 + '</pre>')
        snapshot, _ = await self.capture(offscreen=True)
        node = next(n for n in snapshot['nodes'] if n['tag'] == 'pre')
        self.assertEqual(len(node['subtreeText']), 500)
        self.assertEqual(len(node['directText']), 240)
        self.assertEqual(self.leaf_text(snapshot), '')

    async def test_inline_links_preserve_the_complete_prose(self):
        await self.page('<p>From <a href="#a">Middle English</a> into '
                        '<a href="#b">Medieval Latin</a>, then Arabic.</p>')
        _, model = await self.capture()
        self.assertIn('From Middle English into Medieval Latin , then Arabic.', model)

    async def test_equation_image_labels_survive_rendered_ancestors(self):
        await self.page('<p>The recurrence <img alt="F_n=F_(n-1)+F_(n-2)"> '
                        'has initial conditions <img alt="F_1=F_2=1">.</p>')
        _, model = await self.capture()
        self.assertIn('F_n=F_(n-1)+F_(n-2)', model)
        self.assertIn('F_1=F_2=1', model)

    async def test_table_keeps_superscript_and_subscript_relationships(self):
        await self.page('<table><tr><td>h</td><td>6.62607015 × 10<sup>−34</sup></td>'
                        '<td>m s<sup>−1</sup></td><td>Δν<sub>Cs</sub></td></tr></table>')
        _, model = await self.capture()
        self.assertIn('^{−34}', model)
        self.assertIn('^{−1}', model)
        self.assertIn('_{Cs}', model)
        self.assertIn('6.62607015', model)

    async def test_computed_strikethrough_is_not_an_affirmed_value(self):
        await self.page('<p>Environment: marine, '
                        '<span style="text-decoration:line-through">terrestrial</span>.</p>')
        snapshot, model = await self.capture()
        node = next(n for n in snapshot['nodes'] if n['tag'] == 'span')
        self.assertIn({'name': 'strikethrough', 'value': 'true'}, node['states'])
        self.assertIn('~~terrestrial~~', model)
        self.assertNotIn('~~marine', model)


if __name__ == '__main__':
    unittest.main()
