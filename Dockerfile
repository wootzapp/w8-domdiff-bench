# Browser runtime only: do not copy local runner or Chromium source into it.
ARG DEV_DESKTOP_IMAGE=devjangid/wootzapp-chromium-desktop:latest
FROM ${DEV_DESKTOP_IMAGE}
