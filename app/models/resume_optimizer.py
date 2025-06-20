from pydantic import BaseModel, ConfigDict, Field
from typing import List


class JobSkillsExtractionRequest(BaseModel):
    """
    Request model for extracting skills from job descriptions
    """
    job_description: str = Field(..., description="The job description text to extract skills from")
    
    model_config = ConfigDict(extra="forbid")


class JobSkillsExtractionResponse(BaseModel):
    """
    Response model for job skills extraction
    """
    programming_languages: List[str] = Field(default_factory=list, description="List of programming languages mentioned in the job description")
    rest_of_skills: List[str] = Field(default_factory=list, description="List of other skills mentioned in the job description")
    
    model_config = ConfigDict(from_attributes=True) 