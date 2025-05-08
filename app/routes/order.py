import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func
from pydantic import UUID4
from app.database.session import get_async_session
from app.models.order import Order, OrderOrm, OrderCreate, OrderUpdate, PaginatedOrdersResponse
from starlette import status
import uuid
from datetime import datetime, timedelta, timezone
import random
import string

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/orders",
    tags=["orders"]
)


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: Request,
    order_data: OrderCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a new order.
    Uses client IP as user_id automatically.
    
    Example curl command:
    ```bash
    curl -X POST "http://localhost:8000/v1/orders" \\
      -H "Content-Type: application/json" \\
      -d '{
        "status": "pending",
        "total_amount": 149.97,
        "items": [
          {
            "product_id": "prod-001",
            "quantity": 3,
            "price": 49.99,
            "title": "Wireless Headphones"
          }
        ],
        "shipping_address": {
          "full_name": "John Doe",
          "address_line1": "123 Main Street",
          "city": "New York",
          "state": "NY",
          "postal_code": "10001",
          "country": "USA",
          "phone": "+1-555-123-4567"
        },
        "expected_shipping_date": "2025-05-10T00:00:00Z"
      }'
    ```
    """
    try:
        # Convert Pydantic model to ORM model
        order_dict = order_data.model_dump()
        
        # Set status to pending
        order_dict["status"] = "pending"
        
        # Generate random shipping date between current_date+1 and current_date+7 if not provided
        if not order_data.expected_shipping_date:
            current_date = datetime.now()
            random_seconds = random.randint(1, 180)  # 1 second to 3 minutes
            order_dict["expected_shipping_date"] = current_date + timedelta(seconds=random_seconds)
        
        # Generate a random tracking number
        tracking_prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
        tracking_number = f"{tracking_prefix}{random.randint(10000000, 99999999)}"
        order_dict["tracking_number"] = tracking_number
        
        # Set timestamps
        current_timestamp = datetime.now()
        order_dict["created_at"] = current_timestamp
        order_dict["updated_at"] = current_timestamp
        
        if request.state.client_ip:
            # Add user_id from client IP
            user_id = request.state.client_ip 
            order_dict["user_id"] = user_id
        else:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        
        new_order = OrderOrm(**order_dict)
        
        session.add(new_order)
        await session.commit()
        return None

    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}", response_model=Order)
async def get_order(
    request: Request,
    order_id: UUID4 = Path(..., description="The UUID of the order to retrieve"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get a single order by ID.
    Only allows viewing user's own orders.
    Also updates order status based on current date vs expected shipping date.
    """
    try:
        # Get user_id from client IP
        if not request.state.client_ip:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        
        user_id = request.state.client_ip
        
        # Only allow users to view their own orders
        query = select(OrderOrm).where(OrderOrm.id == order_id, OrderOrm.user_id == user_id)
        result = await session.execute(query)
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found or you don't have permission to view it")
        
        # Check and update order status based on current date vs expected shipping date
        current_date = datetime.now()
        
        if order.status not in ["delivered", "cancelled", "refunded"]:
            if order.expected_shipping_date:
                # If current date is 1 minute after expected shipping date, update to delivered
                if current_date >= (order.expected_shipping_date + timedelta(minutes=1)):
                    order.status = "delivered"
                    await session.commit()
                # If current date is on or after expected shipping date, update to shipped
                elif current_date >= order.expected_shipping_date:
                    order.status = "shipped"
                    await session.commit()
        
        return Order.model_validate(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=PaginatedOrdersResponse)
async def list_orders(
    request: Request,
    status: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    List orders with optional filtering by status.
    Uses client IP as user_id automatically.
    Returns a paginated response.
    Status is dynamically updated based on expected_shipping_date before returning.
    """
    try:
        # Calculate offset from page and size
        offset = (page - 1) * size
        
        # Build base query
        query = select(OrderOrm)
        count_query = select(func.count()).select_from(OrderOrm)
        
        # Get user_id from client IP
        if not request.state.client_ip:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        
        user_id = request.state.client_ip
        
        # Apply filters
        query = query.where(OrderOrm.user_id == user_id)
        count_query = count_query.where(OrderOrm.user_id == user_id)
        
        if status:
            query = query.where(OrderOrm.status == status)
            count_query = count_query.where(OrderOrm.status == status)
        
        # Add sorting and pagination
        query = query.order_by(OrderOrm.created_at.desc()).offset(offset).limit(size)
        
        # Execute queries
        result = await session.execute(query)
        count_result = await session.execute(count_query)
        
        orders = result.scalars().all()
        total_count = count_result.scalar_one()
        
        # Check if there are more orders
        has_more = offset + len(orders) < total_count
        
        # Update status based on expected_shipping_date before returning
        current_date = datetime.now(timezone.utc)
        updated_orders = []
        
        for order in orders:
            # Create a copy of the order as Order model to avoid modifying the database objects
            order_dict = {c.name: getattr(order, c.name) for c in order.__table__.columns}
            order_model = Order.model_validate(order_dict)
            
            # Only update status if not in a final state
            if order_model.status not in ["delivered", "cancelled", "refunded"]:
                if order_model.expected_shipping_date:
                    # If current date is 1 minute after expected shipping date, mark as delivered
                    if current_date >= (order_model.expected_shipping_date + timedelta(minutes=1)):
                        order_model.status = "delivered"
                    # If current date is on or after expected shipping date, mark as shipped
                    elif current_date >= order_model.expected_shipping_date:
                        order_model.status = "shipped"
            
            updated_orders.append(order_model)
        
        # Return paginated response with updated statuses
        return PaginatedOrdersResponse.model_validate({
            "orders": updated_orders,
            "page": page,
            "size": size,
            "has_more": has_more,
            "total_count": total_count
        })
    except Exception as e:
        logger.error(f"Error listing orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{order_id}", response_model=None)
async def update_order(
    request: Request,
    order_data: OrderUpdate,
    order_id: UUID4 = Path(..., description="The UUID of the order to update"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Update an existing order.
    Only allows updating user's own orders.
    """
    try:
        # Get user_id from client IP
        if not request.state.client_ip:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        
        user_id = request.state.client_ip
        
        # Get existing order
        query = select(OrderOrm).where(OrderOrm.id == order_id, OrderOrm.user_id == user_id)
        result = await session.execute(query)
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found or you don't have permission to update it")
        
        # Update only provided fields
        order_dict = order_data.model_dump(exclude_unset=True)
        for key, value in order_dict.items():
            if value is not None:  # Skip None values
                setattr(order, key, value)
        
        await session.commit()
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    request: Request,
    order_id: UUID4 = Path(..., description="The UUID of the order to delete"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Delete an order by ID.
    Only allows deleting user's own orders.
    """
    try:
        # Get user_id from client IP
        if not request.state.client_ip:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        
        user_id = request.state.client_ip
        
        # Check if order exists and belongs to the user
        query = select(OrderOrm).where(OrderOrm.id == order_id, OrderOrm.user_id == user_id)
        result = await session.execute(query)
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found or you don't have permission to delete it")
        
        # Delete the order
        await session.delete(order)
        await session.commit()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting order: {str(e)}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) 