# Browser runtime only: do not copy local runner or Chromium source into it.
ARG DEV_DESKTOP_IMAGE=w8-core:snapshot-diff
FROM ${DEV_DESKTOP_IMAGE}
