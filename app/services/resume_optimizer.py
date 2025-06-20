import logging
import json
from typing import Dict, List
from google import genai
from google.genai.types import GenerateContentConfig, AutomaticFunctionCallingConfig
from app.services.vertex import get_genai_client
from app.models.resume_optimizer import JobSkillsExtractionResponse

logger = logging.getLogger(__name__)


class ResumeOptimizerService:
    """Service for resume optimization using Gemini 2.0 Flash"""
    
    @staticmethod
    async def extract_job_skills(job_description: str) -> JobSkillsExtractionResponse:
        """
        Extract programming languages and other skills from a job description using Gemini 2.0 Flash
        
        Args:
            job_description: The job description text to analyze
            
        Returns:
            JobSkillsExtractionResponse with extracted skills
        """
        try:
            client = get_genai_client()
            
            # Create a detailed prompt for skill extraction
            prompt = f"""
            You are an expert at analyzing job descriptions and extracting the most important technical keywords for ATS (Applicant Tracking System) optimization. 
            Please analyze the following job description and extract exactly 15 technical skills total:
            1. Programming languages mentioned (e.g., Python, JavaScript, Java, C++, etc.)
            2. The most important technical skills mentioned (e.g., frameworks, libraries, tools, databases, cloud platforms, methodologies, etc.)
            
            Job Description:
            {job_description}
            
            Please respond with a JSON object in the following format:
            {{
                "programming_languages": ["language1", "language2", ...],
                "rest_of_skills": ["skill1", "skill2", ...]
            }}
            
            Guidelines:
            - Extract exactly 15 technical skills total (combined programming languages + other skills)
            - PRIORITIZE skills that appear multiple times or are emphasized in the job description
            - EXCLUDE soft skills like communication, teamwork, leadership, problem-solving, etc.
            - For programming languages, include variations (e.g., "JS" should be "JavaScript")
            - Remove duplicates and normalize skill names
            - Focus on skills that are most likely to be searched by ATS systems
            - Include frameworks, libraries, tools, databases, cloud platforms, development methodologies, and technical concepts
            - Examples of high-priority technical skills: React, Django, AWS, Docker, PostgreSQL, Git, CI/CD, REST APIs, GraphQL, Kubernetes, etc.
            - Be selective and accurate - only include the most critical skills mentioned
            """
            
            # Use Gemini 2.0 Flash model
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent extraction
                    max_output_tokens=1000,
                    automatic_function_calling=AutomaticFunctionCallingConfig(
                        disable=True,
                        maximum_remote_calls=0
                    ),
                )
            )
            
            # Parse the response
            response_text = response.text.strip()
            logger.info(f"Gemini response: {response_text}")
            
            try:
                # Clean up any potential markdown code block formatting
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                # Parse JSON response
                skills_data = json.loads(response_text.strip())
                
                # Validate and clean the data
                programming_languages = skills_data.get("programming_languages", [])
                rest_of_skills = skills_data.get("rest_of_skills", [])
                
                # Ensure they are lists and remove empty strings
                programming_languages = [lang.strip() for lang in programming_languages if lang.strip()]
                rest_of_skills = [skill.strip() for skill in rest_of_skills if skill.strip()]
                
                # Define default skills to ensure they're included
                default_programming_languages = ["Python", "Node.js"]
                default_technical_skills = ["Spring Boot", "FastAPI", "PostgreSQL", "SQL", "NoSQL", "AWS", "Docker"]
                
                # Add missing default programming languages
                for default_lang in default_programming_languages:
                    if not any(default_lang.lower() == lang.lower() for lang in programming_languages):
                        programming_languages.append(default_lang)
                
                # Add missing default technical skills
                for default_skill in default_technical_skills:
                    if not any(default_skill.lower() == skill.lower() for skill in rest_of_skills):
                        rest_of_skills.append(default_skill)
                
                # Remove duplicates while preserving order
                programming_languages = list(dict.fromkeys(programming_languages))
                rest_of_skills = list(dict.fromkeys(rest_of_skills))
                
                return JobSkillsExtractionResponse(
                    programming_languages=programming_languages,
                    rest_of_skills=rest_of_skills
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from Gemini: {e}")
                logger.error(f"Raw response: {response_text}")
                
                # Fallback: try to extract skills manually from the response
                return ResumeOptimizerService._fallback_skill_extraction(response_text)
                
        except Exception as e:
            logger.error(f"Error extracting job skills: {str(e)}")
            raise Exception(f"Failed to extract skills from job description: {str(e)}")
    
    @staticmethod
    def _fallback_skill_extraction(response_text: str) -> JobSkillsExtractionResponse:
        """
        Fallback method to extract skills if JSON parsing fails
        """
        logger.warning("Using fallback skill extraction method")
        
        # Simple fallback - return empty lists
        # In a production environment, you might want to implement
        # a more sophisticated fallback parsing mechanism
        return JobSkillsExtractionResponse(
            programming_languages=[],
            rest_of_skills=[]
        ) 