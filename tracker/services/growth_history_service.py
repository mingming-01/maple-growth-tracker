"""성장 기록 저장소에 대한 애플리케이션 서비스."""
class GrowthHistoryService:
    """컨트롤러와 저장소 사이에서 성장 기록 조회·저장 작업을 제공한다."""

    def __init__(self, repository):
        self._repository = repository

    @property
    def backend(self):
        return self._repository.backend

    @property
    def uses_postgres(self):
        return self._repository.uses_postgres

    def get_records(self, ocid, start_date, end_date):
        return self._repository.get_records(ocid, start_date, end_date)

    def save_records(self, ocid, character_name, world_name, records):
        return self._repository.save_records(
            ocid, character_name, world_name, records
        )
