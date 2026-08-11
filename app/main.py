"""ASGI compatibility entry point for the V1 modular application."""

from customer_care.bootstrap import create_app

app = create_app()
