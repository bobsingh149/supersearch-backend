from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
from starlette.middleware.cors import CORSMiddleware
from app.utils.embedding import get_embedding
from app.routes import search_product, product
from app.database.session import check_db_connection
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize model and processor on startup"""
    logger.info("Initializing model and processor...")
    
    # Check database connection
    logger.info("Checking database connection...")
    if not await check_db_connection():
        logger.error("Database connection failed")
        raise RuntimeError("Database connection failed")
    logger.info("Database connection successful")
    
    #get_model()  # This will cache the model
    embedding = await get_embedding("startup")
    print(embedding[:5])
    print("length")
    print(len(embedding))
    logger.info("Initialization complete.")
    
    yield
    
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health",operation_id="root")
def read_root()->dict:
    """health check route"""
    return {"message": "server is healthy!"}

app.include_router(search.router)
app.include_router(product.router)

#TODO
'''

Basic routes needed

(Just do text based first in MVP image will come later)

1. Search 
2. Recommend
    1. suggest similar items (based on item return most similar)
    2. Recommendation based on past purchase activity (precomputed and updated)
3. AI shopping 


Use recraft to get model for your product using image to image

Write blogs specifically to promote your products

It all works because we will sync their data regularly 

https://supabase.com/docs/guides/ai/hybrid-search

Personalized AI shopper in 1 big window modal resumable with AI shopping interface for everything 

On startup feed it user detials

We need to have products data, reviews data, past orders  in our vector db    

knows query intent then call backend for search, otherwise give chat completion 

just keep giving context of whatever product user selects , and like fetch reviews and tell what to style with

It will also generate some template questions based on state

Traditional search bar with AI will also be there


Also add the option of api I could poll to resync the data
 
Value is in taking data or syncing and then applying AI to it

Take data from db url or extrernal api like shopify for now

Use the data in AI 

Chat Support
Customer care support
Product search 

Use the APScheduler for all bg tasks connect with DB

Also release the ai blogger as seperate tool targeted for companies trying to maximize
seo reach suggest them topics based on company product
IDEAS

1. Personalized Shopping Experience
Dynamic Styling Suggestions: Offer styling or pairing suggestions for clothing, accessories, or home decor based on the customer's preferences or purchase history.
Product Recommendations: Recommend products based on browsing history, past purchases, or customer demographics.
Dynamic Search Results: Use natural language processing (NLP) to improve search accuracy and offer filters based on intent.
Custom Homepages: Curate homepage content dynamically based on user interests and browsing habits.
2. Visual AI Applications
Virtual Try-On: Allow customers to visualize products like clothes, glasses, or makeup on themselves using AR/AI.
Style Matching: Suggest similar styles or complementary items for a chosen product.
Image-Based Search: Enable customers to upload a photo and find similar products in the store.
3. Product Management
AI-Powered Styling for Products: Automatically generate photos of products in different styles or settings (e.g., furniture in a living room setup).
Automated Product Tagging: Use AI to classify and tag products with keywords, categories, and attributes for better discoverability.
4. Review Summarization and Analysis
Sentiment Analysis: Summarize customer reviews into pros and cons and identify trending sentiments.
Review Insights: Provide summarized insights from customer reviews to help others make informed decisions.
Fake Review Detection: Use AI to detect fraudulent reviews and ensure authenticity.
5. Marketing and Engagement
Dynamic Pricing: Use AI to adjust prices based on demand, competitor pricing, and inventory levels.
AI-Powered Ad Targeting: Optimize ad campaigns with personalized recommendations and dynamic creatives.
Customer Segmentation: Use AI to segment customers based on behavior and demographics for targeted campaigns.
Automated Content Creation: Generate product descriptions, marketing emails, and blog posts using AI.
6. Customer Support
AI Chatbots: Provide 24/7 customer support for FAQs, order tracking, and issue resolution.
Sentiment-Driven Support Escalation: Detect customer frustration and escalate to a human agent.
Multilingual Support: Translate and respond to customer queries in multiple languages.
7. Logistics and Supply Chain
Demand Forecasting: Predict inventory needs based on sales trends and seasonal factors.
Smart Inventory Management: Optimize stock levels using AI to prevent overstocking or stockouts.
Shipping Optimization: Use AI to choose the fastest or most cost-effective shipping routes.
8. Fraud Detection and Payment Processing
Fraud Prevention: Detect unusual purchase patterns and prevent fraudulent transactions.
Dynamic Payment Gateways: Optimize payment gateway usage based on customer location or past success rates.
9. User Behavior and Analytics
Churn Prediction: Identify customers likely to stop shopping and provide retention offers.
Heatmap Analysis: Analyze customer interaction on the website to optimize the design.
Real-Time Personalization: Modify product listings, banners, and deals as users interact with the site.
10. Customer Retention and Loyalty
AI Loyalty Programs: Reward customers based on AI-driven predictions of their lifetime value.
Personalized Retention Offers: Offer custom discounts or loyalty benefits to retain at-risk customers.
Predictive Recommendations: Suggest subscription or replenishment products based on past purchases.
11. Content Moderation
Automated Moderation: Monitor and filter user-generated content such as reviews, Q&A, or forums to remove spam or inappropriate material.
AI-Curated Reviews: Highlight the most helpful or relevant reviews for new customers.
12. Advanced Analytics
Predictive Trends Analysis: Identify future trends and suggest products to add to the catalog.
Competitor Analysis: Use AI to monitor competitor pricing, stock levels, and trends.
Performance Insights: Provide detailed analytics on marketing, product performance, and customer behavior.
13. Voice and Conversational Commerce
Voice Search Optimization: Allow users to search products using voice commands.
Conversational Agents: Offer shopping assistance through voice-enabled devices like Alexa or Google Assistant.
14. Returns and Post-Sale Support
AI Return Predictions: Predict the likelihood of product returns and adjust policies accordingly.
Smart Returns Process: Suggest alternative solutions like exchanges or troubleshooting steps before processing a return.
Post-Purchase Insights: Provide AI-powered recommendations for accessories or related items post-purchase.
15. Sustainability and CSR
Sustainable Options: Highlight eco-friendly or sustainable product choices using AI.
Carbon Footprint Estimation: Inform customers of the environmental impact of their purchases.


'''