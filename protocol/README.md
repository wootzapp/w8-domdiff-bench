# ChromiumRL Protocol

`ChromiumRL.pdl` is a pinned copy of the protocol definition used by w8-core.
It is included for schema review and tests. Runtime commands are implemented
inside the browser build; the recorder does not execute this source file.

Source repository: `https://github.com/wootzapp/wootzapp-browser`

Source revision: `c519a1fb70d156aff4a12d4c1460e39bf9adf547` (the overlay pin in
[`browser-build.json`](browser-build.json)). The build also checks the pinned
protocol hash and verifies that the copied browser matches the compiled Release
binary. Its actual SHA-256 is recorded in `build/browser-build.json`, which is
included in the image. See the [runbook](../docs/runbook.md) for browser image build
and configuration commands.

