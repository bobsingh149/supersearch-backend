"""Routes for bulk SEO generation."""
import logging
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from app.database.session import get_async_session, get_tenant_name, get_user_id
from app.database.db import Db
from app.models.shopify_bulk_seo.batch_job import BatchJobDB, BatchJobStatus
from app.models.shopify_bulk_seo.batch_product import BatchProductDB, BatchProductStatus
from app.temporal.core.client import get_temporal_client
from app.temporal.workflows.bulk_seo_generate.models import BulkSeoGenerateInput
from app.temporal.workflows.bulk_seo_generate.start_workflow import start_bulk_seo_generate_workflow

from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bulk-seo", tags=["bulk-seo"])

class BulkSeoGenerateRequest(BaseModel):
    """Request model for bulk SEO generation."""
    product_ids: Optional[List[str]] = None
    all_products: bool = False
    batch_name: Optional[str] = None

class BulkSeoGenerateResponse(BaseModel):
    """Response model for bulk SEO generation."""
    batch_job_id: str
    workflow_id: str
    run_id: str
    message: str

@router.post("/generate", response_model=BulkSeoGenerateResponse)
async def start_bulk_seo_generation(
    bulk_request: BulkSeoGenerateRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name),
    temporal_client: Client = Depends(get_temporal_client)
):
    """
    Start bulk SEO generation for Shopify products.

    Args:
        bulk_request: Bulk SEO generation request
        session: Database session
        tenant: Tenant name
        temporal_client: Temporal client

    Returns:
        Response with batch job ID and workflow details
    """
    logger.info(f"Starting bulk SEO generation for user: {user_id}")

    # Validate input
    if not bulk_request.product_ids and not bulk_request.all_products:
        raise HTTPException(
            status_code=400,
            detail="Either product_ids or all_products=true must be specified"
        )

    if bulk_request.product_ids and bulk_request.all_products:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both product_ids and all_products=true"
        )
    

    # Create batch job record
    batch_job_id = str(uuid.uuid4())
    batch_name = bulk_request.batch_name or f"Bulk SEO Generation - {datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M')}"

    await Db.insert(
        session=session,
        tenant=tenant,
        table_name=BatchJobDB.__tablename__,
        columns=[
            BatchJobDB.id.name,
            BatchJobDB.name.name,
            BatchJobDB.payload.name,
            BatchJobDB.status.name
        ],
        values={
            BatchJobDB.id.name: batch_job_id,
            BatchJobDB.name.name: batch_name,
            BatchJobDB.payload.name: {
                "shopify_user_id": user_id,
                "product_ids": bulk_request.product_ids,
                "all_products": bulk_request.all_products,
            },
            BatchJobDB.status.name: BatchJobStatus.PENDING.value
        }
    )

    await session.commit()

    logger.info(f"Created batch job: {batch_job_id}")

    # Create batch product records for specified product IDs with pending status
    if bulk_request.product_ids:
        batch_products_data = [
            {
                BatchProductDB.batch_id.name: batch_job_id,
                BatchProductDB.product_id.name: product_id,
                BatchProductDB.status.name: BatchProductStatus.PENDING.value
            }
            for product_id in bulk_request.product_ids
        ]

        await Db.bulk_insert(
            session=session,
            tenant=tenant,
            table_name=BatchProductDB.__tablename__,
            columns=[
                BatchProductDB.batch_id.name,
                BatchProductDB.product_id.name,
                BatchProductDB.status.name
            ],
            items=batch_products_data
        )

        await session.commit()
        logger.info(f"Created {len(bulk_request.product_ids)} batch product records with pending status")

    # Start temporal workflow
    try:
        workflow_input = BulkSeoGenerateInput(
            product_ids=bulk_request.product_ids,
            all_products=bulk_request.all_products,
            shopify_user_id=user_id,
            batch_job_id=batch_job_id,
            tenant=tenant
        )
        
        workflow_result = await start_bulk_seo_generate_workflow(
            client=temporal_client,
            input_data=workflow_input
        )
        
        logger.info(f"Started workflow: {workflow_result['workflow_id']}")
        
        return BulkSeoGenerateResponse(
            batch_job_id=batch_job_id,
            workflow_id=workflow_result['workflow_id'],
            run_id=workflow_result['run_id'],
            message="Bulk SEO generation started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting workflow: {str(e)}")
        
        # Update batch job status to failed
        failed_payload = {
            "shopify_user_id": user_id,
            "product_ids": bulk_request.product_ids,
            "all_products": bulk_request.all_products,
            "error": str(e)
        }
        await Db.update(
            session=session,
            tenant=tenant,
            table_name=BatchJobDB.__tablename__,
            id_field=BatchJobDB.id.name,
            id_value=batch_job_id,
            updates={
                BatchJobDB.status.name: BatchJobStatus.FAILED.value,
                BatchJobDB.payload.name: failed_payload,
                BatchJobDB.updated_at.name: datetime.now(datetime.UTC)
            }
        )
        await session.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start bulk SEO generation: {str(e)}"
        )

@router.get("/status/{batch_job_id}")
async def get_batch_status(
    batch_job_id: str,
    session: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name),
    user_id: str = Depends(get_user_id)
):
    """
    Get the status of a bulk SEO generation batch.

    Args:
        batch_job_id: Batch job ID
        session: Database session
        tenant: Tenant name

    Returns:
        Batch status and progress information
    """
    # Get batch job
    batch_job = await Db.get_by_id(
        session=session,
        tenant=tenant,
        table_name=BatchJobDB.__tablename__,
        id_field=BatchJobDB.id.name,
        id_value=batch_job_id
    )

    if not batch_job:
        raise HTTPException(
            status_code=404,
            detail=f"Batch job not found: {batch_job_id}"
        )

    # Get batch products for progress tracking
    batch_products = await Db.get_all(
        session=session,
        tenant=tenant,
        table_name=BatchProductDB.__tablename__,
        filters={BatchProductDB.batch_id.name: batch_job_id}
    )

    # Calculate progress
    total_products = len(batch_products)
    completed_products = sum(1 for bp in batch_products if bp.status == 'completed')
    failed_products = sum(1 for bp in batch_products if bp.status == 'failed')
    pending_products = sum(1 for bp in batch_products if bp.status in ['pending', 'processing'])

    return {
        "batch_job_id": batch_job_id,
        "name": batch_job.name,
        "status": batch_job.status,
        "created_at": batch_job.created_at,
        "updated_at": batch_job.updated_at,
        "progress": {
            "total_products": total_products,
            "completed_products": completed_products,
            "failed_products": failed_products,
            "pending_products": pending_products,
            "completion_percentage": round((completed_products / total_products * 100) if total_products > 0 else 0, 2)
        },
        "payload": batch_job.payload
    }
