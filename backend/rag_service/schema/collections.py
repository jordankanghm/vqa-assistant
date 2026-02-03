from weaviate.classes.config import Configure, DataType, Property, VectorDistances

def create_collections(collections, client):
    for cls_name in collections:
        if not client.collections.exists(cls_name):
            print(f"Creating {cls_name}")
            
            if cls_name == "Summary":
                properties = [
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="chunkIds", data_type=DataType.TEXT_ARRAY),
                ]

            else:  # Chunk
                properties = [
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="summaryId", data_type=DataType.TEXT),
                ]
            
            client.collections.create(
                name=cls_name,
                properties=properties,
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE
                )
            )
            print(f"Created {cls_name} with vector index")

        else:
            print(f"Collection {cls_name} exists")

def delete_collections(collections, client):
    for collection_name in collections:
        client.collections.delete(
            collection_name
        )

        print(f"Deleted collection: {collection_name}")

    print(f"Collections deleted: {collections}")
