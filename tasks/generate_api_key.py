import sys
sys.path.append("..")
from lib.models import APIConsumer
from lib import generate_keys
key, secret = generate_keys()
a = APIConsumer.create(api_key=key, api_secret=secret)
a.save()
print("Key: %s" % key)
print("Secret: %s" % secret)