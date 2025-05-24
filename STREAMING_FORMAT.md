# Streaming Response Format Documentation

## Overview

The shopping assistant now uses a predictable JSON streaming format that makes it easy for the frontend to parse responses without errors. Each chunk of the stream is a valid JSON object with a consistent structure.

## Streaming Response Structure

Each streaming response chunk follows this JSON structure:

```json
{
  "type": "content|questions|products|complete",
  "conversation_id": "string",
  "content": "string|array"
}
```

## Response Types

### 1. Content (`type: "content"`)
Contains the main response text from the assistant.

```json
{
  "type": "content",
  "conversation_id": "conv_123",
  "content": "Here are some great laptops for you..."
}
```

### 2. Questions (`type: "questions"`)
Contains follow-up questions suggested by the assistant.

```json
{
  "type": "questions", 
  "conversation_id": "conv_123",
  "content": [
    "What's your budget for the laptop?",
    "Do you need it for gaming or work?",
    "Would you prefer Windows or Mac?"
  ]
}
```

### 3. Products (`type: "products"`)
Contains product information referenced in the response.

```json
{
  "type": "products",
  "conversation_id": "conv_123", 
  "content": [
    {
      "id": "laptop123",
      "title": "Gaming Laptop Pro",
      "custom_data": {...},
      "ai_summary": {...},
      "reviews": [...]
    }
  ]
}
```

### 4. Complete (`type: "complete"`)
Signals that the stream has ended.

```json
{
  "type": "complete",
  "conversation_id": "conv_123",
  "content": "stream_complete"
}
```

## Stream Order

The streaming responses will always arrive in this order:

1. **Multiple `content` chunks** - The main response text, streamed as it's generated
2. **One `questions` chunk** - Follow-up questions (if any)
3. **One `products` chunk** - Referenced products (if any)
4. **One `complete` chunk** - Stream completion marker

## Frontend Implementation Example

```javascript
async function handleStreamingResponse(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  let mainContent = '';
  let questions = [];
  let products = [];
  let isComplete = false;
  
  try {
    while (!isComplete) {
      const { done, value } = await reader.read();
      
      if (done) break;
      
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter(line => line.trim());
      
      for (const line of lines) {
        try {
          const data = JSON.parse(line);
          
          switch (data.type) {
            case 'content':
              mainContent += data.content;
              // Update UI with new content
              updateMainContent(mainContent);
              break;
              
            case 'questions':
              questions = data.content;
              // Display follow-up questions
              displayQuestions(questions);
              break;
              
            case 'products':
              products = data.content;
              // Display referenced products
              displayProducts(products);
              break;
              
            case 'complete':
              isComplete = true;
              // Stream is complete
              onStreamComplete();
              break;
          }
        } catch (parseError) {
          console.error('Error parsing JSON:', parseError);
        }
      }
    }
  } catch (error) {
    console.error('Streaming error:', error);
  }
}
```

## Error Handling

- Each line in the stream is a complete JSON object
- If a line fails to parse, it can be safely ignored without affecting other chunks
- The `complete` marker ensures you know when the stream has ended
- All chunks include the `conversation_id` for correlation

## Benefits

1. **Predictable Structure**: Every chunk follows the same JSON schema
2. **Error Resilient**: Failed parsing of one chunk doesn't break the entire stream
3. **Type Safety**: Clear type indicators for different content types
4. **Completion Detection**: Explicit completion marker
5. **Frontend Friendly**: Easy to implement progressive UI updates

## Migration from Old Format

The old format used text markers like `follow_up_questions:` and `product_ids:`. The new format:

- Eliminates parsing ambiguity
- Provides structured data instead of text parsing
- Includes explicit completion signaling
- Maintains the same semantic information but in a more reliable format 