WebTiles server modifications

Added bot API endpoints for AI controller.

Changes:

/bot/state
- added turn
- added last_activity_time

/bot/log
- tail read from:
/data/rcs/<username>/<username>.txt

Used for AI observation pipeline.