import json
import datetime
import os
from peewee import Model, CharField, BooleanField, DateTimeField, fn
from playhouse.shortcuts import model_to_dict
from lib import get_banned_counties
from playhouse.db_url import connect

db = connect(os.environ['DATABASE_URL'])


class BaseModel(Model):
    class Meta:
        database = db

    def to_json(self):
        d = {k: v.isoformat() if isinstance(v, datetime.datetime) else v for k, v in model_to_dict(self).items() if k != "id"}
        return json.dumps(d)


class County(BaseModel):
    name = CharField(unique=True)
    burn_ban = BooleanField()
    updated_date = DateTimeField(null=True)

    @classmethod
    def _get_earliest_update(cls):
        return cls.select(fn.Min(cls.updated_date)).scalar()

    @classmethod
    def update_bans(cls):
        last_update = cls._get_earliest_update()

        if (not last_update) or last_update < (datetime.datetime.utcnow() - datetime.timedelta(seconds=1)):
            counties = get_banned_counties()
            with cls._meta.database.atomic():
                cls.update(burn_ban=False, updated_date=datetime.datetime.utcnow()).execute()
                cls.update(burn_ban=True, updated_date=datetime.datetime.utcnow()).where(County.name << counties).execute()


class APIConsumer(BaseModel):
    api_key = CharField(unique=True)
    api_secret = CharField(unique=True)
