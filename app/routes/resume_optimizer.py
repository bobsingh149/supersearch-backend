import logging
from fastapi import APIRouter, HTTPException, status
from app.models.resume_optimizer import (
    JobSkillsExtractionRequest,
    JobSkillsExtractionResponse
)
from app.services.resume_optimizer import ResumeOptimizerService

router = APIRouter(
    prefix="/resume-optimizer",
    tags=["resume-optimizer"]
)

logger = logging.getLogger(__name__)


@router.post("/extract-job-skills", response_model=JobSkillsExtractionResponse)
async def extract_job_skills(
    request: JobSkillsExtractionRequest
) -> JobSkillsExtractionResponse:
    """
    Extract programming languages and other skills from a job description using Gemini 2.0 Flash.
    
    This endpoint analyzes the provided job description and extracts:
    - Programming languages mentioned in the description
    - All other technical and non-technical skills
    
    Args:
        request: JobSkillsExtractionRequest containing the job description
        
    Returns:
        JobSkillsExtractionResponse with extracted programming languages and other skills
        
    Raises:
        HTTPException: If the job description is empty or if extraction fails
    """
    try:
        # Validate input
        if not request.job_description.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description cannot be empty"
            )
        
        logger.info(f"Extracting skills from job description of length: {len(request.job_description)}")
        
        # Extract skills using Gemini 2.0 Flash
        result = await ResumeOptimizerService.extract_job_skills(request.job_description)
        
        logger.info(
            f"Successfully extracted {len(result.programming_languages)} programming languages "
            f"and {len(result.rest_of_skills)} other skills"
        )
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in extract_job_skills endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract skills from job description: {str(e)}"
        ) 