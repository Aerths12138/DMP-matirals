"""Build RAG chunks for attachments uploaded before research RAG was enabled.

Run from ``backend`` after migrations, for example:
``python -m scripts.reindex_research_knowledge``.
Use ``--all`` after changing an extractor or chunk configuration.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.file import File
from app.services.file_storage_service import get_storage_backend
from app.services import research_knowledge_service


async def reindex(include_ready: bool) -> None:
    storage = get_storage_backend()
    async with async_session() as db:
        query = select(File).order_by(File.created_at.asc())
        if not include_ready:
            query = query.where(File.knowledge_status != "ready")
        files = (await db.execute(query)).scalars().all()
        print(f"Reindexing {len(files)} attachment(s)…")
        for file in files:
            try:
                raw = await storage.download(file.stored_path)
                result = await research_knowledge_service.index_file_bytes(db, file, raw)
            except Exception as exc:
                file.knowledge_status = "failed"
                file.knowledge_chunk_count = 0
                file.knowledge_error = research_knowledge_service._error_message(exc)
                result = research_knowledge_service.index_status(file)
            await db.commit()
            print(f"{file.original_name}: {result['status']} ({result['chunk_count']} chunks)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Materials DMP research RAG chunks")
    parser.add_argument("--all", action="store_true", help="also rebuild attachments already indexed")
    args = parser.parse_args()
    asyncio.run(reindex(args.all))


if __name__ == "__main__":
    main()
