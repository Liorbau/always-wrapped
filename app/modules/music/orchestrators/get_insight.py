from app.modules.music import insight_service, mappers


def execute():
    return mappers.insight_to_dto(insight_service.pick())
