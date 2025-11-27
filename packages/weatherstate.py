from datetime import datetime, timezone

# Shared scheduler state for weather events (UTC datetimes)
next_event_time = None  # datetime in UTC when next event will start
next_event_name = None
current_event_end_time = None  # datetime in UTC when current event ends
current_event_name = None


def set_next_event(dt: datetime, name: str | None):
    global next_event_time, next_event_name
    next_event_time = dt
    next_event_name = name


def clear_next_event():
    global next_event_time, next_event_name
    next_event_time = None
    next_event_name = None


def set_current_event_end(dt: datetime, name: str | None):
    global current_event_end_time, current_event_name
    current_event_end_time = dt
    current_event_name = name


def clear_current_event():
    global current_event_end_time, current_event_name
    current_event_end_time = None
    current_event_name = None


def get_state():
    # Return raw datetime objects (or None) so callers can format/compute deltas
    return {
        "next_event_time": next_event_time,
        "next_event_name": next_event_name,
        "current_event_end_time": current_event_end_time,
        "current_event_name": current_event_name,
    }
