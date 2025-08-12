from typing import Any
from datetime import datetime
from bson import ObjectId
from app.models.generals import Pagination
import json


def JsonObjectFormatter(obj: Any):
    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, datetime):
        return str(obj)

    raise TypeError("%r is not JSON serializable" % obj)


async def GetDistinctData(v_db_collection, v_query=None, v_field="_id"):
    if v_query is not None:
        cursor = v_db_collection.distinct(v_field, v_query)
    else:
        cursor = v_db_collection.distinct(v_field)
    result = await cursor
    return result


async def GetDataCount(v_db_collection, v_query={}):
    count: int = await v_db_collection.count_documents(v_query)
    return count


async def GetOneData(
    v_db_collection,
    v_query={},
    v_projection={},
    sort_by=None,
    sort_direction=-1,
    is_json=True,
):
    sort_value = []
    if sort_by:
        sort_value.append((sort_by, sort_direction))

    cursor = v_db_collection.find_one(v_query, v_projection, sort=sort_value)
    result = await cursor
    if is_json:
        result = json.dumps(result, default=JsonObjectFormatter)
        result = json.loads(result)

    return result


async def GetAggregateData(v_db_collection, v_pipeline: list = [], v_projection={}):
    pipeline = v_pipeline.copy()
    if v_projection:
        pipeline.append({"$project": v_projection})
    result = await v_db_collection.aggregate(pipeline).to_list(None)
    result = json.dumps(result, default=JsonObjectFormatter)
    result = json.loads(result)

    return result


async def GetManyData(
    v_db_collection, v_query, v_projection={}, v_pagination: Pagination = {}
):
    query = []
    query_facet = v_query.copy()
    if v_pagination:
        query.append({"$skip": (v_pagination["page"] - 1) * v_pagination["items"]})
        query.append({"$limit": v_pagination["items"]})

    if v_projection:
        query.append({"$project": v_projection})

    query_facet.append(
        {
            "$facet": {
                "data": query,
                "data_info": [{"$count": "count"}],
            }
        }
    )

    query_facet.append(
        {
            "$project": {
                "_id": 0,
                "data": "$data",
                "count": {"$arrayElemAt": ["$data_info.count", 0]},
            }
        }
    )
    result = await v_db_collection.aggregate(query_facet).to_list(None)
    result = json.dumps(result, default=JsonObjectFormatter)
    result = json.loads(result)
    data = []
    if "data" in result[0]:
        data = result[0]["data"]

    count = 0
    if "count" in result[0]:
        count = result[0]["count"]

    return data, count


async def CreateOneData(v_db_collection, v_data):
    result = await v_db_collection.insert_one(v_data)
    return result


async def CreateManyData(v_db_collection, v_data):
    result = await v_db_collection.insert_many(v_data)
    return result


async def UpdateOneData(v_db_collection, v_query, v_update, upsert: bool = False):
    result = await v_db_collection.update_one(v_query, v_update, upsert)
    return result


async def UpdateManyData(v_db_collection, v_query, v_update):
    result = await v_db_collection.update_many(v_query, v_update)
    return result


async def DeleteOneData(v_db_collection, v_query):
    result = await v_db_collection.delete_one(v_query)
    return result


async def DeleteManyData(v_db_collection, v_query):
    result = await v_db_collection.delete_many(v_query)
    return result


async def GetPipelineDataCount(v_db_collection, v_query=[]):
    cursor = v_db_collection.aggregate(v_query)
    result = await cursor.to_list(length=None)
    if result:
        count = result[0].get("count", 0)
        return count
    else:
        return 0
