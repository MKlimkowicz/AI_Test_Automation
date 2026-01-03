
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger
from utils.vector_store import VectorStore, QueryResult, get_vector_store
from utils.config import config

logger = get_logger(__name__)

COLLECTION_CODE_CHUNKS = "code_chunks"

@dataclass
class CodeChunk:
    content: str
    file_path: str
    chunk_type: str  # function, class, module, config
    name: str
    start_line: int
    end_line: int

@dataclass
class RAGResult:
    chunk: CodeChunk
    similarity: float
    relevance_score: float

class CodeRAG:

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_vector_store()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        self.vector_store.get_or_create_collection(COLLECTION_CODE_CHUNKS)

    def _extract_chunks(self, code: str, file_path: str) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        lines = code.split('\n')

        func_pattern = r'^(async\s+)?def\s+(\w+)\s*\([^)]*\).*?:'
        current_func = None
        func_start = 0
        func_lines: List[str] = []

        for i, line in enumerate(lines):
            func_match = re.match(func_pattern, line)
            if func_match:
                if current_func and func_lines:
                    chunks.append(CodeChunk(
                        content='\n'.join(func_lines),
                        file_path=file_path,
                        chunk_type="function",
                        name=current_func,
                        start_line=func_start + 1,
                        end_line=i
                    ))
                current_func = func_match.group(2)
                func_start = i
                func_lines = [line]
            elif current_func:
                if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                    chunks.append(CodeChunk(
                        content='\n'.join(func_lines),
                        file_path=file_path,
                        chunk_type="function",
                        name=current_func,
                        start_line=func_start + 1,
                        end_line=i
                    ))
                    current_func = None
                    func_lines = []
                else:
                    func_lines.append(line)

        if current_func and func_lines:
            chunks.append(CodeChunk(
                content='\n'.join(func_lines),
                file_path=file_path,
                chunk_type="function",
                name=current_func,
                start_line=func_start + 1,
                end_line=len(lines)
            ))

        class_pattern = r'^class\s+(\w+).*?:'
        current_class = None
        class_start = 0
        class_lines: List[str] = []

        for i, line in enumerate(lines):
            class_match = re.match(class_pattern, line)
            if class_match:
                if current_class and class_lines:
                    chunks.append(CodeChunk(
                        content='\n'.join(class_lines),
                        file_path=file_path,
                        chunk_type="class",
                        name=current_class,
                        start_line=class_start + 1,
                        end_line=i
                    ))
                current_class = class_match.group(1)
                class_start = i
                class_lines = [line]
            elif current_class:
                if line.strip() and not line.startswith(' ') and not line.startswith('\t') and not line.startswith('#'):
                    chunks.append(CodeChunk(
                        content='\n'.join(class_lines),
                        file_path=file_path,
                        chunk_type="class",
                        name=current_class,
                        start_line=class_start + 1,
                        end_line=i
                    ))
                    current_class = None
                    class_lines = []
                else:
                    class_lines.append(line)

        if current_class and class_lines:
            chunks.append(CodeChunk(
                content='\n'.join(class_lines),
                file_path=file_path,
                chunk_type="class",
                name=current_class,
                start_line=class_start + 1,
                end_line=len(lines)
            ))

        if not chunks:
            chunk_size = config.CODE_CHUNK_SIZE
            for i in range(0, len(lines), chunk_size):
                chunk_lines = lines[i:i + chunk_size]
                if any(line.strip() for line in chunk_lines):
                    chunks.append(CodeChunk(
                        content='\n'.join(chunk_lines),
                        file_path=file_path,
                        chunk_type="module",
                        name=f"chunk_{i // chunk_size}",
                        start_line=i + 1,
                        end_line=min(i + chunk_size, len(lines))
                    ))

        return chunks

    def _create_chunk_signature(self, chunk: CodeChunk) -> str:
        elements = [chunk.chunk_type, chunk.name]

        identifiers = re.findall(r'\b([a-z_][a-z0-9_]*)\b', chunk.content.lower())
        keywords = {'def', 'class', 'return', 'if', 'else', 'for', 'while', 'import', 'from', 'self', 'None', 'True', 'False'}
        meaningful = [id for id in identifiers if id not in keywords and len(id) > 2]
        elements.extend(meaningful[:20])  # Limit to prevent too long signature

        return ' '.join(elements)

    def index_file(self, file_path: str, code: str) -> int:
        chunks = self._extract_chunks(code, file_path)

        if not chunks:
            return 0

        texts = []
        metadatas = []
        ids = []

        for chunk in chunks:
            signature = self._create_chunk_signature(chunk)
            chunk_id = f"{file_path}:{chunk.name}:{chunk.start_line}"

            texts.append(signature)
            metadatas.append({
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "content": chunk.content[:2000],  # Limit stored content
            })
            ids.append(self.vector_store.embedding_service.text_hash(chunk_id))

        self.vector_store.add(COLLECTION_CODE_CHUNKS, texts, metadatas, ids)
        logger.debug(f"Indexed {len(chunks)} chunks from {file_path}")
        return len(chunks)

    def index_directory(
        self,
        directory: Path,
        extensions: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, int]:
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.go', '.rb', '.php']

        if exclude_patterns is None:
            exclude_patterns = ['test_', '_test.', 'tests/', '__pycache__', 'node_modules', '.git']

        stats = {"files": 0, "chunks": 0}

        for ext in extensions:
            for file_path in directory.rglob(f"*{ext}"):
                str_path = str(file_path)
                if any(pattern in str_path for pattern in exclude_patterns):
                    continue

                try:
                    code = file_path.read_text(errors='ignore')
                    if code.strip():
                        num_chunks = self.index_file(str(file_path), code)
                        if num_chunks > 0:
                            stats["files"] += 1
                            stats["chunks"] += num_chunks
                except Exception as e:
                    logger.warning(f"Failed to index {file_path}: {e}")

        logger.info(f"Indexed {stats['chunks']} chunks from {stats['files']} files")
        return stats

    def query(
        self,
        query_text: str,
        n_results: int = None,
        chunk_type: Optional[str] = None
    ) -> List[RAGResult]:
        if n_results is None:
            n_results = config.RAG_MAX_CHUNKS

        where_filter = None
        if chunk_type:
            where_filter = {"chunk_type": chunk_type}

        results = self.vector_store.query(
            COLLECTION_CODE_CHUNKS,
            query_text,
            n_results=n_results,
            where=where_filter
        )

        rag_results = []
        for result in results:
            chunk = CodeChunk(
                content=result.metadata.get("content", ""),
                file_path=result.metadata.get("file_path", ""),
                chunk_type=result.metadata.get("chunk_type", "unknown"),
                name=result.metadata.get("name", ""),
                start_line=int(result.metadata.get("start_line", 0)),
                end_line=int(result.metadata.get("end_line", 0)),
            )
            rag_results.append(RAGResult(
                chunk=chunk,
                similarity=result.similarity,
                relevance_score=result.similarity
            ))

        return rag_results

    def get_context_for_scenario(
        self,
        scenario: str,
        category: str,
        n_chunks: int = None
    ) -> str:
        if n_chunks is None:
            n_chunks = config.RAG_MAX_CHUNKS

        query = f"{category} {scenario}"
        results = self.query(query, n_results=n_chunks)

        if not results:
            return ""

        context_parts = []
        for result in results:
            chunk = result.chunk
            context_parts.append(
                f"# From {chunk.file_path}:{chunk.start_line} ({chunk.chunk_type} {chunk.name})\n"
                f"{chunk.content}"
            )

        return "\n\n".join(context_parts)

    def get_context_for_analysis(
        self,
        app_type: str,
        n_chunks: int = 10
    ) -> str:
        type_queries = {
            "rest_api": "api endpoint route handler request response",
            "cli": "command argument parser main entry",
            "library": "public function class interface export",
            "graphql": "resolver query mutation schema type",
            "grpc": "service method proto handler",
            "websocket": "socket connection message event handler",
            "message_queue": "queue consumer producer message handler",
            "serverless": "lambda handler event context function",
            "batch_script": "main process batch job task",
        }

        query = type_queries.get(app_type, "main function class handler")
        results = self.query(query, n_results=n_chunks)

        if not results:
            return ""

        context_parts = []
        seen_files = set()

        for result in results:
            chunk = result.chunk
            if chunk.file_path in seen_files:
                continue
            seen_files.add(chunk.file_path)

            context_parts.append(
                f"## {chunk.file_path}\n"
                f"```python\n{chunk.content}\n```"
            )

        return "\n\n".join(context_parts)

    def get_stats(self) -> Dict[str, Any]:
        stats = self.vector_store.collection_stats(COLLECTION_CODE_CHUNKS)
        return {
            "total_chunks": stats.count,
            "collection_name": stats.name,
        }

    def clear(self) -> None:
        self.vector_store.delete_collection(COLLECTION_CODE_CHUNKS)
        self._ensure_collection()
        logger.info("Cleared code index")

_default_rag: Optional[CodeRAG] = None

def get_code_rag(vector_store: Optional[VectorStore] = None) -> CodeRAG:
    global _default_rag

    if _default_rag is None:
        _default_rag = CodeRAG(vector_store)

    return _default_rag
