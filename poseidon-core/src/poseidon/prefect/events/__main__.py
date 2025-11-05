"""Module entrypoint for streaming Prefect events via the event router."""

from poseidon.prefect.events.event_router import listen_to_prefect_events

if __name__ == "__main__":  # pragma: no cover
    listen_to_prefect_events()
