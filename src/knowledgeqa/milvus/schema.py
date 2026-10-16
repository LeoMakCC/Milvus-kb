from __future__ import annotations

from pymilvus import DataType, Function, FunctionType


def collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def create_knowledge_base_collection(client, kb_id: str, dim: int) -> None:
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(
        "text",
        DataType.VARCHAR,
        max_length=8192,
        enable_analyzer=True,
        analyzer_params={"type": "chinese"},
    )
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("kb_id", DataType.VARCHAR, max_length=64)
    schema.add_field("document_id", DataType.VARCHAR, max_length=64)
    schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
    schema.add_field("page_no", DataType.INT64)
    schema.add_field("doc_type", DataType.VARCHAR, max_length=32)
    schema.add_field("source_type", DataType.VARCHAR, max_length=32)
    schema.add_function(
        Function(
            name="bm25",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse"],
            params={},
        )
    )

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    index_params.add_index(
        field_name="sparse",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
    )
    client.create_collection(
        collection_name(kb_id),
        schema=schema,
        index_params=index_params,
    )
