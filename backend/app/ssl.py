"""Use the OS trust store for HTTPS (fixes macOS Python SSL verify failures)."""


def configure_ssl() -> None:
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
