"""
History Service: Manages user analysis history queries and storage.
Provides clean interface for history operations with proper error handling.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
import models1 as models
import schema as schemas
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func

class HistoryService:
    """Handles history retrieval and management operations."""

    @staticmethod
    def get_user_history(
        db: Session, username: str, limit: int = 50
    ) -> Optional[schemas.HistoryListResponse]:
        """
        Retrieve user's analysis history with pagination.
        
        Args:
            db: Database session
            username: Username to fetch history for
            limit: Maximum number of items to return
            
        Returns:
            HistoryListResponse with items and total count
        """
        items = (
            db.query(models.History)
            .filter(models.History.username == username)
            .order_by(desc(models.History.created_at))
            .limit(limit)
            .all()
        )
        
        total = db.query(models.History).filter(
            models.History.username == username
        ).count()

        history_items = [
            schemas.HistoryItem.model_validate(item) for item in items
        ]

        return schemas.HistoryListResponse(
            username=username,
            items=history_items,
            total=total,
        )

    @staticmethod
    async def get_user_history_async(
        db: AsyncSession, username: str, limit: int = 50
    ) -> Optional[schemas.HistoryListResponse]:
        """
        Retrieve user's analysis history asynchronously.
        """
        stmt = (
            select(models.History)
            .where(models.History.username == username)
            .order_by(desc(models.History.created_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        count_stmt = select(func.count()).select_from(models.History).where(models.History.username == username)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()

        history_items = [
            schemas.HistoryItem.model_validate(item) for item in items
        ]

        return schemas.HistoryListResponse(
            username=username,
            items=history_items,
            total=total,
        )

    @staticmethod
    def save_analysis(
        db: Session, history_data: schemas.SaveInput
    ) -> models.History:
        """
        Save analysis result to history.
        
        Args:
            db: Database session
            history_data: Analysis data to save
            
        Returns:
            Created History record
        """
        history_record = models.History(
            username=history_data.username,
            text=history_data.text[:500],  # Limit to 500 chars
            score=history_data.score,
            label=history_data.label,
            source_url=history_data.source_url,
            confidence=history_data.confidence,
        )
        db.add(history_record)
        db.commit()
        db.refresh(history_record)
        return history_record

    @staticmethod
    def get_user_stats(db: Session, username: str) -> dict:
        """
        Get aggregate statistics for a user's analysis history.
        
        Args:
            db: Database session
            username: Username to get stats for
            
        Returns:
            Dict with stats (total_analyses, avg_score, verdict_breakdown)
        """
        history = db.query(models.History).filter(
            models.History.username == username
        ).all()

        total = len(history)
        if total == 0:
            return {
                "total_analyses": 0,
                "average_score": 0.0,
                "verdict_breakdown": {"True": 0, "False": 0, "Uncertain": 0},
            }

        avg_score = sum(h.score for h in history) / total

        verdict_breakdown = {
            "True": sum(1 for h in history if h.label == "True"),
            "False": sum(1 for h in history if h.label == "False"),
            "Uncertain": sum(1 for h in history if h.label == "Uncertain"),
        }

        return {
            "total_analyses": total,
            "average_score": round(avg_score, 1),
            "verdict_breakdown": verdict_breakdown,
        }

    @staticmethod
    def delete_history_item(db: Session, item_id: int, username: str) -> bool:
        """
        Delete a specific history item (if owned by user).
        
        Args:
            db: Database session
            item_id: History item ID to delete
            username: Username making the request
            
        Returns:
            True if deleted, False if not found or unauthorized
        """
        item = db.query(models.History).filter(
            models.History.id == item_id
        ).first()

        if not item or item.username != username:
            return False

        db.delete(item)
        db.commit()
        return True

    @staticmethod
    async def clear_user_history_async(db: AsyncSession, username: str) -> bool:
        """
        Delete all history items for a specific user asynchronously.
        """
        from sqlalchemy import delete
        stmt = delete(models.History).where(models.History.username == username)
        await db.execute(stmt)
        await db.commit()
        return True
