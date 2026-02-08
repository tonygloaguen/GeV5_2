#!/bin/bash
sleep 20                   # laisse le Pi booter
export DISPLAY=:0          # s’assure qu’on pointe sur :0

chromium-browser \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-features=OverscrollHistoryNavigation,TouchpadOverscrollHistoryNavigation \
  --overscroll-history-navigation=0 \
  --noerrdialogs \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  --incognito \
  --start-fullscreen http://127.0.0.1:5002/data/channels
