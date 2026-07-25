from app.modules.music import records_service


def execute(tz="UTC"):
    return {"records": records_service.build(tz)}
