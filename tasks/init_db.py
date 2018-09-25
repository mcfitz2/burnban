import sys
sys.path.append("..")

from playhouse.db_url import connect
import os
from models import APIConsumer, County

db = connect(os.environ['DATABASE_URL'])
db.execute_sql("DROP TABLE county CASCADE;")
db.execute_sql("DROP TABLE apiconsumer CASCADE;")
db.create_tables([County, APIConsumer])
sql_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'initialize.sql')
with open(sql_path, 'r') as sql_file:
    db.execute_sql(sql_file.read())