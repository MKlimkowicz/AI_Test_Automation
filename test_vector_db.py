#!/usr/bin/env python3
"""Test script for Vector DB infrastructure - Stage 1 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_embedding_service():
    """Test the embedding service."""
    print("\n" + "=" * 60)
    print("Testing EmbeddingService...")
    print("=" * 60)

    from utils.embeddings import EmbeddingService, get_embedding_service

    # Test initialization
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")
    print(f"✓ EmbeddingService initialized with model: {service.model_name}")

    # Test single embedding
    text = "This is a test sentence for embedding."
    embedding = service.embed_single(text)
    print(f"✓ Single embedding generated, dimension: {len(embedding)}")
    assert len(embedding) == 384, f"Expected 384 dimensions, got {len(embedding)}"

    # Test batch embedding
    texts = [
        "First test sentence",
        "Second test sentence",
        "Third completely different text about programming"
    ]
    embeddings = service.embed(texts)
    print(f"✓ Batch embedding generated: {len(embeddings)} embeddings")
    assert len(embeddings) == 3

    # Test similarity
    sim_same = service.similarity(embeddings[0], embeddings[1])
    sim_diff = service.similarity(embeddings[0], embeddings[2])
    print(f"✓ Similarity between similar texts: {sim_same:.4f}")
    print(f"✓ Similarity between different texts: {sim_diff:.4f}")
    assert sim_same > sim_diff, "Similar texts should have higher similarity"

    # Test text hash
    hash1 = service.text_hash("test text")
    hash2 = service.text_hash("test text")
    hash3 = service.text_hash("different text")
    assert hash1 == hash2, "Same text should produce same hash"
    assert hash1 != hash3, "Different text should produce different hash"
    print(f"✓ Text hashing works correctly")

    # Test singleton pattern
    service2 = get_embedding_service()
    service3 = get_embedding_service()
    assert service2 is service3, "Singleton should return same instance"
    print(f"✓ Singleton pattern works correctly")

    print("\n✅ EmbeddingService tests PASSED")
    return True


def test_vector_store():
    """Test the vector store."""
    print("\n" + "=" * 60)
    print("Testing VectorStore...")
    print("=" * 60)

    from utils.vector_store import VectorStore, get_vector_store, QueryResult

    # Create temporary directory for persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"

        # Test initialization
        store = VectorStore(persist_dir=persist_dir)
        print(f"✓ VectorStore initialized at: {persist_dir}")

        # Test collection creation
        collection_name = "test_collection"
        collection = store.get_or_create_collection(collection_name)
        print(f"✓ Collection '{collection_name}' created")

        # Test adding documents
        texts = [
            "def test_login(): assert login('user', 'pass') == True",
            "def test_logout(): assert logout() == True",
            "def test_api_response(): response = api.get('/users'); assert response.status == 200",
            "def test_database_connection(): conn = db.connect(); assert conn.is_open()",
            "def test_file_upload(): result = upload('test.txt'); assert result.success"
        ]
        metadatas = [
            {"type": "auth", "category": "functional"},
            {"type": "auth", "category": "functional"},
            {"type": "api", "category": "integration"},
            {"type": "database", "category": "integration"},
            {"type": "file", "category": "functional"}
        ]

        ids = store.add(collection_name, texts, metadatas)
        print(f"✓ Added {len(ids)} documents to collection")

        # Test collection stats
        stats = store.collection_stats(collection_name)
        print(f"✓ Collection stats: {stats.count} documents")
        assert stats.count == 5

        # Test query
        query = "test user authentication login"
        results = store.query(collection_name, query, n_results=3)
        print(f"✓ Query returned {len(results)} results")
        assert len(results) == 3

        # Verify results are QueryResult objects with expected fields
        top_result = results[0]
        assert isinstance(top_result, QueryResult)
        assert top_result.similarity > 0
        print(f"✓ Top result: similarity={top_result.similarity:.4f}")
        print(f"  Text: {top_result.text[:50]}...")

        # Test query_similar with threshold
        similar_results = store.query_similar(collection_name, query, threshold=0.3, n_results=5)
        print(f"✓ Query similar (threshold=0.3): {len(similar_results)} results above threshold")

        # Test get_by_id
        retrieved = store.get_by_id(collection_name, ids[0])
        assert retrieved is not None
        assert retrieved.text == texts[0]
        print(f"✓ Retrieved document by ID successfully")

        # Test update
        update_success = store.update(
            collection_name,
            ids[0],
            text="def test_login_updated(): assert login('admin', 'secret') == True",
            metadata={"type": "auth", "category": "security", "updated": True}
        )
        assert update_success
        print(f"✓ Document updated successfully")

        # Verify update
        updated = store.get_by_id(collection_name, ids[0])
        assert "updated" in updated.text
        print(f"✓ Update verified")

        # Test delete
        delete_success = store.delete(collection_name, ids=[ids[4]])
        assert delete_success
        stats_after_delete = store.collection_stats(collection_name)
        assert stats_after_delete.count == 4
        print(f"✓ Document deleted, count now: {stats_after_delete.count}")

        # Test list collections
        collections = store.list_collections()
        assert collection_name in collections
        print(f"✓ List collections: {collections}")

        # Test delete collection
        store.delete_collection(collection_name)
        collections_after = store.list_collections()
        assert collection_name not in collections_after
        print(f"✓ Collection deleted successfully")

    print("\n✅ VectorStore tests PASSED")
    return True


def test_config_integration():
    """Test config integration."""
    print("\n" + "=" * 60)
    print("Testing Config Integration...")
    print("=" * 60)

    from utils.config import config

    # Check vector DB settings exist
    assert hasattr(config, 'ENABLE_VECTOR_DB')
    assert hasattr(config, 'VECTOR_DB_PATH')
    assert hasattr(config, 'EMBEDDING_MODEL')
    assert hasattr(config, 'HEALING_SIMILARITY_THRESHOLD')
    assert hasattr(config, 'DEDUP_VECTOR_THRESHOLD')
    assert hasattr(config, 'CLASSIFICATION_SIMILARITY_THRESHOLD')
    assert hasattr(config, 'RAG_MAX_CHUNKS')
    assert hasattr(config, 'CODE_CHUNK_SIZE')

    print(f"✓ ENABLE_VECTOR_DB: {config.ENABLE_VECTOR_DB}")
    print(f"✓ VECTOR_DB_PATH: {config.VECTOR_DB_PATH}")
    print(f"✓ EMBEDDING_MODEL: {config.EMBEDDING_MODEL}")
    print(f"✓ HEALING_SIMILARITY_THRESHOLD: {config.HEALING_SIMILARITY_THRESHOLD}")
    print(f"✓ DEDUP_VECTOR_THRESHOLD: {config.DEDUP_VECTOR_THRESHOLD}")
    print(f"✓ CLASSIFICATION_SIMILARITY_THRESHOLD: {config.CLASSIFICATION_SIMILARITY_THRESHOLD}")

    print("\n✅ Config Integration tests PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VECTOR DB INFRASTRUCTURE - STAGE 1 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_config_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Config Integration tests FAILED: {e}")
        all_passed = False

    try:
        if not test_embedding_service():
            all_passed = False
    except Exception as e:
        print(f"\n❌ EmbeddingService tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_vector_store():
            all_passed = False
    except Exception as e:
        print(f"\n❌ VectorStore tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STAGE 1 TESTS PASSED!")
        print("Vector DB infrastructure is ready for integration.")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
