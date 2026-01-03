#!/usr/bin/env python3
"""Test script for Code RAG - Stage 5 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_code_rag():
    """Test the CodeRAG."""
    print("\n" + "=" * 60)
    print("Testing CodeRAG...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.code_rag import CodeRAG, CodeChunk, RAGResult

    # Create temporary directory for persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        vector_store = VectorStore(persist_dir=persist_dir)
        rag = CodeRAG(vector_store=vector_store)

        print(f"✓ CodeRAG initialized")

        # Test indexing a code file
        sample_code = '''
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:5000"


def get_users() -> Dict[str, Any]:
    """Get all users from the API."""
    response = requests.get(f"{BASE_URL}/api/users")
    response.raise_for_status()
    return response.json()


def create_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user."""
    response = requests.post(f"{BASE_URL}/api/users", json=data)
    response.raise_for_status()
    return response.json()


def delete_user(user_id: str) -> bool:
    """Delete a user by ID."""
    response = requests.delete(f"{BASE_URL}/api/users/{user_id}")
    return response.status_code == 204


class UserService:
    """Service for user operations."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def authenticate(self, username: str, password: str) -> str:
        """Authenticate user and return token."""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        return response.json()["token"]

    def get_profile(self, token: str) -> Dict[str, Any]:
        """Get user profile."""
        response = requests.get(
            f"{self.base_url}/api/profile",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()
'''
        num_chunks = rag.index_file("api_client.py", sample_code)
        print(f"✓ Indexed {num_chunks} chunks from sample code")
        assert num_chunks >= 2, f"Expected at least 2 chunks, got {num_chunks}"

        # Test indexing another file
        cli_code = '''
import click
import sys


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file")
def main(verbose: bool, config: str):
    """Main CLI entry point."""
    if verbose:
        click.echo("Verbose mode enabled")
    if config:
        click.echo(f"Using config: {config}")
    click.echo("Processing...")


def process_data(input_file: str, output_file: str) -> int:
    """Process data from input to output."""
    with open(input_file, "r") as f:
        data = f.read()
    # Process...
    with open(output_file, "w") as f:
        f.write(data.upper())
    return 0


if __name__ == "__main__":
    main()
'''
        num_chunks2 = rag.index_file("cli_tool.py", cli_code)
        print(f"✓ Indexed {num_chunks2} chunks from CLI code")

        # Test querying
        results = rag.query("user authentication login", n_results=3)
        print(f"✓ Query returned {len(results)} results")
        assert len(results) >= 1, "Should find at least one result"

        top_result = results[0]
        assert isinstance(top_result, RAGResult)
        assert isinstance(top_result.chunk, CodeChunk)
        print(f"  Top result: {top_result.chunk.name} from {top_result.chunk.file_path}")
        print(f"  Similarity: {top_result.similarity:.3f}")

        # Test query by chunk type
        results_func = rag.query("get users", chunk_type="function", n_results=5)
        print(f"✓ Function-only query returned {len(results_func)} results")

        results_class = rag.query("user service", chunk_type="class", n_results=5)
        print(f"✓ Class-only query returned {len(results_class)} results")

        # Test get_context_for_scenario
        context = rag.get_context_for_scenario(
            "verify user login with valid credentials",
            "functional"
        )
        print(f"✓ get_context_for_scenario returned {len(context)} chars")
        if context:
            print(f"  Context preview: {context[:100]}...")

        # Test get_context_for_analysis
        api_context = rag.get_context_for_analysis("rest_api", n_chunks=5)
        print(f"✓ get_context_for_analysis (rest_api): {len(api_context)} chars")

        cli_context = rag.get_context_for_analysis("cli", n_chunks=5)
        print(f"✓ get_context_for_analysis (cli): {len(cli_context)} chars")

        # Test stats
        stats = rag.get_stats()
        print(f"✓ RAG Stats: {stats}")
        assert stats["total_chunks"] >= 4, f"Expected at least 4 chunks, got {stats['total_chunks']}"

        # Test clear
        rag.clear()
        stats_after = rag.get_stats()
        assert stats_after["total_chunks"] == 0
        print(f"✓ RAG cleared successfully")

    print("\n✅ CodeRAG tests PASSED")
    return True


def test_chunk_extraction():
    """Test code chunk extraction."""
    print("\n" + "=" * 60)
    print("Testing Chunk Extraction...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.code_rag import CodeRAG

    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        vector_store = VectorStore(persist_dir=persist_dir)
        rag = CodeRAG(vector_store=vector_store)

        # Test with code that has multiple functions and classes
        complex_code = '''
class OrderService:
    def __init__(self, db):
        self.db = db

    def create_order(self, user_id, items):
        order = {"user_id": user_id, "items": items}
        return self.db.insert(order)

    def get_order(self, order_id):
        return self.db.find_one(order_id)


def validate_order(order):
    if not order.get("items"):
        raise ValueError("Order must have items")
    return True


async def process_payment(order_id, amount):
    # Async payment processing
    await charge_card(amount)
    return {"status": "success", "order_id": order_id}
'''
        chunks = rag._extract_chunks(complex_code, "order_service.py")
        print(f"✓ Extracted {len(chunks)} chunks from complex code")

        chunk_types = [c.chunk_type for c in chunks]
        chunk_names = [c.name for c in chunks]
        print(f"  Types: {chunk_types}")
        print(f"  Names: {chunk_names}")

        assert "class" in chunk_types, "Should extract class"
        assert "function" in chunk_types, "Should extract functions"

    print("\n✅ Chunk Extraction tests PASSED")
    return True


def test_analyzer_integration():
    """Test the analyzer integration with CodeRAG."""
    print("\n" + "=" * 60)
    print("Testing Analyzer RAG Integration...")
    print("=" * 60)

    from ai_engine.analyzer import _get_code_rag, _index_code_for_rag, _get_rag_context

    # Check that functions are available
    assert callable(_get_code_rag), "_get_code_rag should be callable"
    assert callable(_index_code_for_rag), "_index_code_for_rag should be callable"
    assert callable(_get_rag_context), "_get_rag_context should be callable"
    print(f"✓ Analyzer RAG integration functions are available")

    from utils.config import config
    if config.ENABLE_VECTOR_DB:
        rag = _get_code_rag()
        if rag is not None:
            print(f"✓ _get_code_rag() returned a RAG instance")
            stats = rag.get_stats()
            print(f"  Current chunks indexed: {stats.get('total_chunks', 0)}")
        else:
            print(f"✓ _get_code_rag() returned None (deps not fully loaded)")
    else:
        print(f"✓ Vector DB disabled, skipping RAG initialization test")

    print("\n✅ Analyzer Integration tests PASSED")
    return True


def test_generator_integration():
    """Test the test generator integration with CodeRAG."""
    print("\n" + "=" * 60)
    print("Testing Test Generator RAG Integration...")
    print("=" * 60)

    from ai_engine.test_generator import _get_code_rag, _get_rag_context_for_scenarios

    # Check that functions are available
    assert callable(_get_code_rag), "_get_code_rag should be callable"
    assert callable(_get_rag_context_for_scenarios), "_get_rag_context_for_scenarios should be callable"
    print(f"✓ Test generator RAG integration functions are available")

    print("\n✅ Test Generator Integration tests PASSED")
    return True


def main():
    """Run all Stage 5 tests."""
    print("\n" + "=" * 60)
    print("CODE RAG - STAGE 5 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_code_rag():
            all_passed = False
    except Exception as e:
        print(f"\n❌ CodeRAG tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_chunk_extraction():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Chunk Extraction tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_analyzer_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Analyzer Integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_generator_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Test Generator Integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STAGE 5 TESTS PASSED!")
        print("Code RAG is ready for use.")
        print("\nThe RAG will now:")
        print("  - Index application code into searchable chunks")
        print("  - Provide relevant code context during analysis")
        print("  - Enhance test generation with code snippets")
        print("  - Support app-type-specific context retrieval")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
