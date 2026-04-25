"""Root app shim for OpenEnv CLI workflows."""

from legacy_cobol_env.server.app import app


def main() -> None:
    from legacy_cobol_env.server.app import main as legacy_main

    legacy_main()


if __name__ == "__main__":
    main()


__all__ = ["app", "main"]
