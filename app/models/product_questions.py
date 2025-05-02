from pydantic import BaseModel, model_validator, ConfigDict
from typing import List

class ProductQuestionOutput(BaseModel):
    """Structured output for product questions"""
    questions: List[str]
    
    @model_validator(mode='after')
    def validate_questions(self) -> 'ProductQuestionOutput':
        if not isinstance(self.questions, list):
            raise ValueError("Questions must be a list")
        return self
    
    model_config = ConfigDict(from_attributes=True)

class ProductQuestionsResponse(BaseModel):
    """API response model for product questions"""
    questions: List[str]
    
    model_config = ConfigDict(from_attributes=True) 