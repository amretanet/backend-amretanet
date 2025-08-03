from app.modules.crud_operations import GetManyData


async def GetNearestODP(db, longitude: float, latitude: float):
    if longitude == 0 and latitude == 0:
        return None

    pipeline = [
        {
            "$addFields": {
                "distance": {
                    "$let": {
                        "vars": {
                            "r": 6371000,
                            "lat1": {"$degreesToRadians": latitude},
                            "lon1": {"$degreesToRadians": longitude},
                            "lat2": {"$degreesToRadians": "$location.latitude"},
                            "lon2": {"$degreesToRadians": "$location.longitude"},
                        },
                        "in": {
                            "$multiply": [
                                "$$r",
                                {
                                    "$acos": {
                                        "$add": [
                                            {
                                                "$multiply": [
                                                    {"$sin": "$$lat1"},
                                                    {"$sin": "$$lat2"},
                                                ]
                                            },
                                            {
                                                "$multiply": [
                                                    {"$cos": "$$lat1"},
                                                    {"$cos": "$$lat2"},
                                                    {
                                                        "$cos": {
                                                            "$subtract": [
                                                                "$$lon2",
                                                                "$$lon1",
                                                            ]
                                                        }
                                                    },
                                                ]
                                            },
                                        ]
                                    }
                                },
                            ]
                        },
                    }
                }
            }
        },
        {"$sort": {"distance": 1}},
        {"$limit": 1},
    ]
    odp, _ = await GetManyData(db.odp, pipeline)
    near_odp = odp[0] if len(odp) > 0 else None
    return near_odp
