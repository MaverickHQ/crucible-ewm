from services.core.agentcore_memory.store import DynamoDBMemoryStore


class _FakeDdbClient:
    def __init__(self):
        self.storage = {}
        self.put_calls = 0
        self.get_calls = 0

    def put_item(self, *, TableName, Item):
        self.put_calls += 1
        self.storage[(TableName, Item["pk"]["S"], Item["sk"]["S"])] = Item
        return {"ok": True}

    def get_item(self, *, TableName, Key, ConsistentRead):
        self.get_calls += 1
        item = self.storage.get((TableName, Key["pk"]["S"], Key["sk"]["S"]))
        return {"Item": item} if item else {}


def test_dynamodb_memory_store_round_trip():
    fake = _FakeDdbClient()
    store = DynamoDBMemoryStore(table_name="memory-table", ttl_seconds=3600, client=fake)

    store.put("alpha", {"value": "hello"})
    value = store.get("alpha")

    assert fake.put_calls == 1
    assert fake.get_calls == 1
    assert value == {"value": "hello"}
