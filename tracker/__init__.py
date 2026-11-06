"""Maple Growth Tracker 애플리케이션 패키지."""


def create_app(test_config=None):
    """앱 팩토리를 지연 로딩해 패키지 초기화 순환을 방지한다."""
    from tracker.application import create_app as factory

    return factory(test_config)


__all__ = ["create_app"]
