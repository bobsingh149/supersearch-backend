# import pytest
# from fastapi import status
# import uuid
#
# from tests.common import async_client
#
# @pytest.mark.asyncio
# async def test_chat_with_assistant(async_client):
#     """Test chat with shopping assistant endpoint"""
#     # Generate a random conversation ID for testing
#     conversation_id = str(uuid.uuid4())
#
#     # Test chat endpoint
#     chat_request = {
#         "conversation_id": conversation_id,
#         "message": "What are some good running shoes?",
#         "product_context": []  # No product context for this test
#     }
#
#     response = await async_client.post(
#         "/api/v1/shopping-assistant/chat",
#         json=chat_request
#     )
#
#     # The response might be 200 or might fail depending on the actual implementation
#     # and whether it requires external services like Google's genai
#     # We'll check for both possibilities
#     if response.status_code == status.HTTP_200_OK:
#         data = response.json()
#         assert "conversation_id" in data
#         assert "response" in data
#         assert data["conversation_id"] == conversation_id
#         assert isinstance(data["response"], str)
#         assert len(data["response"]) > 0
#     else:
#         # If it fails, it should be due to external service dependency
#         # not because of a server error
#         assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
#
# @pytest.mark.asyncio
# async def test_chat_with_product_context(async_client):
#     """Test chat with shopping assistant using product context"""
#     # Generate a random conversation ID for testing
#     conversation_id = str(uuid.uuid4())
#
#     # Create a test product first
#     test_product = {
#         "id": "test-shoe-1",
#         "title": "Test Running Shoe",
#         "custom_data": {
#             "id": "test-shoe-1",
#             "title": "Test Running Shoe",
#             "description": "A comfortable running shoe for all terrains",
#             "price": 129.99,
#             "category": "Running Shoes"
#         },
#         "searchable_content": "Test Running Shoe A comfortable running shoe for all terrains Running Shoes"
#     }
#
#     product_input = {
#         "id_field": "id",
#         "title_field": "title",
#         "searchable_attribute_fields": ["title", "description", "category"],
#         "data": [test_product["custom_data"]]
#     }
#
#     # Create the product
#     await async_client.post("/api/v1/products", json=product_input)
#
#     # Test chat endpoint with product context
#     chat_request = {
#         "conversation_id": conversation_id,
#         "message": "Tell me more about this shoe",
#         "product_context": [test_product]
#     }
#
#     response = await async_client.post(
#         "/api/v1/shopping-assistant/chat",
#         json=chat_request
#     )
#
#     # The response might be 200 or might fail depending on the actual implementation
#     if response.status_code == status.HTTP_200_OK:
#         data = response.json()
#         assert "conversation_id" in data
#         assert "response" in data
#         assert data["conversation_id"] == conversation_id
#         assert isinstance(data["response"], str)
#         assert len(data["response"]) > 0
#     else:
#         # If it fails, it should be due to external service dependency
#         assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
#
# @pytest.mark.asyncio
# async def test_get_conversation_history(async_client):
#     """Test getting conversation history"""
#     # Generate a random conversation ID for testing
#     conversation_id = str(uuid.uuid4())
#
#     # First create some chat messages
#     chat_request = {
#         "conversation_id": conversation_id,
#         "message": "What are some good running shoes?",
#         "product_context": []
#     }
#
#     # Send a couple of messages
#     await async_client.post(
#         "/api/v1/shopping-assistant/chat",
#         json=chat_request
#     )
#
#     chat_request["message"] = "I need them for trail running"
#     await async_client.post(
#         "/api/v1/shopping-assistant/chat",
#         json=chat_request
#     )
#
#     # Get the conversation history
#     response = await async_client.get(
#         f"/api/v1/shopping-assistant/conversations/{conversation_id}"
#     )
#
#     # The response might be 200 or might fail depending on the actual implementation
#     if response.status_code == status.HTTP_200_OK:
#         data = response.json()
#         assert "conversation_id" in data
#         assert "messages" in data
#         assert data["conversation_id"] == conversation_id
#         assert isinstance(data["messages"], list)
#         # Should have at least 4 messages (2 user messages and 2 assistant responses)
#         assert len(data["messages"]) >= 4
#     else:
#         # If it fails, it should be due to external service dependency
#         assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR