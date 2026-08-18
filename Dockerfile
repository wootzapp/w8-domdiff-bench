# Browser runtime only: do not copy local runner or Chromium source into it.
ARG DEV_DESKTOP_IMAGE=wootz-runtime:snapshot-diff
FROM ${DEV_DESKTOP_IMAGE}
