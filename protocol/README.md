# ChromiumRL Protocol

`ChromiumRL.pdl` is a pinned copy of the protocol definition used by w8-core.
It is included for schema review and tests. Runtime commands are implemented
inside the browser build; the recorder does not execute this source file.

Source repository: `https://github.com/wootzapp/wootzapp-browser`

Source revision: `79ef492157bd3089f27ab0f8453ecc5227677252` (the overlay pin in
[`browser-build.json`](browser-build.json)). The build also checks the protocol
and browser binary hashes from that file. See the [runbook](../docs/runbook.md)
for browser image build and configuration commands.

