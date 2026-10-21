"""
Chroma 컬렉션 생성·색인·조회. 도메인을 모르는 공통 모듈 — 컬렉션 이름은 config.yaml collections.<key>.
"""
from functools import lru_cache

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.llm import get_embeddings
from backend.settings import get_config, path

UPSERT_BATCH = 100


@lru_cache
def get_client() -> chromadb.ClientAPI:
    chroma_dir = path("chroma_dir")
    chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))


def collection_name(key: str) -> str:
    return get_config()["collections"][key]


def get_store(key: str, embeddings=None) -> Chroma:
    """key = "meta" | "docs". embeddings를 안 주면 .env 설정으로 만든다."""
    return Chroma(
        client=get_client(),
        collection_name=collection_name(key),
        embedding_function=embeddings or get_embeddings(),
    )


def count(key: str) -> int:
    """색인 건수. 임베딩·API 키 없이도 동작한다 (/api/status용). 컬렉션이 없으면 0."""
    name = collection_name(key)
    if name not in [c.name for c in get_client().list_collections()]:
        return 0
    return get_client().get_collection(name).count()


def clean_metadata(meta: dict) -> dict:
    """Chroma는 None 값을 받지 않는다 → 키를 뺀다."""
    return {k: v for k, v in meta.items() if v is not None}


def upsert(store: Chroma, ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
    """같은 ID는 덮어쓴다 (재색인해도 건수 불변)."""
    for i in range(0, len(ids), UPSERT_BATCH):
        store.add_texts(
            texts=texts[i:i + UPSERT_BATCH],
            metadatas=[clean_metadata(m) for m in metadatas[i:i + UPSERT_BATCH]],
            ids=ids[i:i + UPSERT_BATCH],
        )


def all_ids(store: Chroma, where: dict | None = None) -> list[str]:
    return store.get(where=where, include=[])["ids"]


def delete(store: Chroma, ids: list[str]) -> None:
    if ids:
        store.delete(ids=ids)


def exists(store: Chroma, where: dict) -> bool:
    return bool(store.get(where=where, limit=1, include=[])["ids"])


def split_with_offsets(text: str) -> list[tuple[int, str]]:
    """[(시작 위치, 청크)] — config.yaml chunk.size / chunk.overlap. 위치는 원문 기준."""
    cfg = get_config()["chunk"]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["size"], chunk_overlap=cfg["overlap"], add_start_index=True,
    )
    return [(d.metadata["start_index"], d.page_content) for d in splitter.create_documents([text])]


def get_metadatas(store: Chroma, where: dict) -> list[tuple[str, dict]]:
    """[(청크 ID, 메타데이터)] — 임베딩 없이 조건으로만 가져온다."""
    r = store.get(where=where, include=["metadatas"])
    return list(zip(r["ids"], r["metadatas"]))


def get_by_ids(store: Chroma, ids: list[str]) -> list[Document]:
    r = store.get(ids=ids, include=["documents", "metadatas"])
    found = {i: Document(id=i, page_content=d, metadata=m)
             for i, d, m in zip(r["ids"], r["documents"], r["metadatas"])}
    return [found[i] for i in ids if i in found]


def search(store: Chroma, query: str, k: int, where: dict | None = None,
           mmr: bool = False, fetch_k: int = 20, lambda_mult: float = 0.5) -> list[Document]:
    """유사도 Top-k 또는 MMR. 반환 Document.id = 청크 ID."""
    if mmr:
        return store.max_marginal_relevance_search(query, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, filter=where)
    return store.similarity_search(query, k=k, filter=where)
