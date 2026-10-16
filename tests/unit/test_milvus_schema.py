from knowledgeqa.milvus.schema import collection_name, create_knowledge_base_collection


class FakeSchema:
    def __init__(self) -> None:
        self.fields = []
        self.functions = []

    def add_field(self, *args, **kwargs) -> None:
        self.fields.append((args, kwargs))

    def add_function(self, function) -> None:
        self.functions.append(function)


class FakeIndexParams:
    def __init__(self) -> None:
        self.indexes = []

    def add_index(self, **kwargs) -> None:
        self.indexes.append(kwargs)


class FakeClient:
    def __init__(self) -> None:
        self.schema = FakeSchema()
        self.indexes = FakeIndexParams()
        self.collections = []

    def create_schema(self, **kwargs) -> FakeSchema:
        self.schema_kwargs = kwargs
        return self.schema

    def prepare_index_params(self) -> FakeIndexParams:
        return self.indexes

    def create_collection(self, name, schema, index_params) -> None:
        self.collections.append((name, schema, index_params))


def test_collection_name_is_prefixed() -> None:
    assert collection_name("abc") == "kb_abc"


def test_create_knowledge_base_collection_builds_expected_contract() -> None:
    client = FakeClient()

    create_knowledge_base_collection(client, "abc", 512)

    assert client.schema_kwargs["auto_id"] is True
    assert client.collections[0][0] == "kb_abc"
    field_names = [field[0][0] for field in client.schema.fields]
    assert field_names == [
        "id",
        "vector",
        "text",
        "sparse",
        "kb_id",
        "document_id",
        "chunk_id",
        "page_no",
        "doc_type",
        "source_type",
        "source_path",
    ]
    assert len(client.schema.functions) == 1
    assert client.indexes.indexes[0]["field_name"] == "vector"
    assert client.indexes.indexes[1]["field_name"] == "sparse"
