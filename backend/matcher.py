import os
import sys
from pathlib import Path

# Add the current directory to the Python path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from models import JobInfo, CandidateInfo, MatchRecord
from bson.objectid import ObjectId
from anthropic import Anthropic
import os
import json
import re
from dotenv import load_dotenv
from fastapi import HTTPException
from database import db

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Load environment variables from .env in the backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Initialize Anthropic client
try:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not found in environment variables")
        anthropic_client = None
    else:
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Anthropic client: {str(e)}")
    anthropic_client = None

def parse_duration(duration: str) -> float:
    """
    Parse duration string into years.
    Handles formats like:
    - "March 2003 – January 2005"
    - "2 years"
    - "6 months"
    - "2015-2020"
    """
    try:
        # Handle month-year format
        if '–' in duration or '-' in duration:
            parts = duration.split('–') if '–' in duration else duration.split('-')
            if len(parts) == 2:
                start = parts[0].strip()
                end = parts[1].strip()
                
                # Extract years
                start_year = None
                end_year = None
                
                # Try to extract years from dates
                for part in [start, end]:
                    year_match = re.search(r'\b(19|20)\d{2}\b', part)
                    if year_match:
                        if start_year is None:
                            start_year = int(year_match.group())
                        else:
                            end_year = int(year_match.group())
                
                if start_year and end_year:
                    return end_year - start_year
                
        # Handle "X years" format
        year_match = re.search(r'(\d+)\s*(?:year|yr|y)', duration.lower())
        if year_match:
            return float(year_match.group(1))
            
        # Handle "X months" format
        month_match = re.search(r'(\d+)\s*(?:month|mo|m)', duration.lower())
        if month_match:
            return float(month_match.group(1)) / 12
            
        # Handle year range format (e.g., "2015-2020")
        range_match = re.search(r'(\d{4})\s*-\s*(\d{4})', duration)
        if range_match:
            start_year = int(range_match.group(1))
            end_year = int(range_match.group(2))
            return end_year - start_year
            
    except Exception as e:
        logger.warning(f"Failed to parse duration '{duration}': {str(e)}")
        return 0.0
        
    return 0.0

def calculate_python_score(job: JobInfo, candidate: CandidateInfo) -> float:
    """
    Calculate a basic matching score between a job and candidate using Python heuristics.
    Returns a score between 0 and 100.
    """
    score = 0
    max_score = 100
    weights = {
        'skills': 0.3,
        'experience': 0.3,
        'education': 0.2,
        'completeness': 0.1,
        'current_role': 0.1
    }

    # Determine role type from job title and requirements
    role_type = "other"
    job_text = f"{job.title} {job.summary} {' '.join(job.requirements or [])} {' '.join(job.skills or [])}".lower()
    
    technical_indicators = ['engineer', 'developer', 'programmer', 'data', 'cloud', 'azure', 'aws', 'python', 'java', 'sql', 'devops']
    hr_indicators = ['hr', 'human resources', 'recruitment', 'talent', 'people', 'employee']
    finance_indicators = ['finance', 'accounting', 'financial', 'audit', 'tax']
    
    if any(indicator in job_text for indicator in technical_indicators):
        role_type = "technical"
    elif any(indicator in job_text for indicator in hr_indicators):
        role_type = "hr"
    elif any(indicator in job_text for indicator in finance_indicators):
        role_type = "finance"

    # Skills matching (30%)
    if job.skills and candidate.skills:
        job_skills = set(skill.lower() for skill in job.skills)
        candidate_skills = set(skill.lower() for skill in candidate.skills)
        
        # Role-specific skill matching
        if role_type == "technical":
            technical_skills = {'python', 'java', 'sql', 'azure', 'aws', 'cloud', 'data', 'devops', 'ci/cd', 'spark', 'pyspark'}
            candidate_technical_skills = candidate_skills.intersection(technical_skills)
            skill_matches = len(job_skills.intersection(candidate_technical_skills))
        elif role_type == "hr":
            hr_skills = {'hr', 'recruitment', 'talent', 'employee', 'people', 'management', 'leadership'}
            candidate_hr_skills = candidate_skills.intersection(hr_skills)
            skill_matches = len(job_skills.intersection(candidate_hr_skills))
        else:
            skill_matches = len(job_skills.intersection(candidate_skills))
            
        skill_score = (skill_matches / len(job_skills)) * 100 if job_skills else 0
        score += skill_score * weights['skills']

    # Experience matching (30%)
    if job.requirements and candidate.experience:
        total_years = 0
        relevant_years = 0
        current_role_match = False
        
        for exp in candidate.experience:
            if 'duration' in exp:
                duration = exp['duration']
                if isinstance(duration, str):
                    years = parse_duration(duration)
                    total_years += years
                    
                    # Check if experience is relevant to role type
                    exp_text = f"{exp.get('job_title', '').lower()} {exp.get('company', '').lower()} {' '.join(exp.get('responsibilities', []))}"
                    
                    if role_type == "technical":
                        if any(indicator in exp_text for indicator in technical_indicators):
                            relevant_years += years
                            # Check if this is the current role
                            if 'present' in duration.lower() or 'current' in duration.lower():
                                current_role_match = True
                    elif role_type == "hr":
                        if any(indicator in exp_text for indicator in hr_indicators):
                            relevant_years += years
                            if 'present' in duration.lower() or 'current' in duration.lower():
                                current_role_match = True
                    elif role_type == "finance":
                        if any(indicator in exp_text for indicator in finance_indicators):
                            relevant_years += years
                            if 'present' in duration.lower() or 'current' in duration.lower():
                                current_role_match = True
        
        # Score based on relevant experience
        exp_score = min(100, (relevant_years / 5) * 100) if total_years > 0 else 0
        score += exp_score * weights['experience']
        
        # Add bonus for current role match
        if current_role_match:
            score += 100 * weights['current_role']

    # Education matching (20%)
    if job.requirements and candidate.education:
        has_relevant_education = False
        for edu in candidate.education:
            degree = edu.get('degree', '').lower()
            institution = edu.get('institution', '').lower()
            
            if role_type == "technical":
                if any(term in degree for term in ['computer', 'engineering', 'science', 'technology', 'data']):
                    has_relevant_education = True
                    break
            elif role_type == "hr":
                if any(term in degree for term in ['human resources', 'psychology', 'business', 'management']):
                    has_relevant_education = True
                    break
            elif role_type == "finance":
                if any(term in degree for term in ['finance', 'accounting', 'business', 'economics']):
                    has_relevant_education = True
                    break
        
        score += (100 if has_relevant_education else 0) * weights['education']

    # Completeness (10%)
    completeness_score = 0
    if candidate.name:
        completeness_score += 20
    if candidate.experience:
        completeness_score += 20
    if candidate.education:
        completeness_score += 20
    if candidate.skills:
        completeness_score += 20
    if candidate.summary:
        completeness_score += 20
    score += completeness_score * weights['completeness']

    return round(score, 2)

def get_claude_match(job: JobInfo, candidate: CandidateInfo) -> Optional[Dict[str, Any]]:
    """
    Get matching assessment from Claude AI.
    Returns None if Claude is not available or fails.
    """
    if not anthropic_client:
        logger.warning("Anthropic client not available")
        return None

    try:
        system_prompt = """You are a recruitment assistant. Your task is to:
        1. First analyze the job description to determine the role type (e.g., IT, HR, Finance, etc.)
        2. Then assess the candidate's fit for that specific role type
        3. Return a JSON object with:
           - match_score (0-100)
           - shortlist (true/false)
           - strengths (list of 1-3 bullet points)
           - gaps (list of 1-3 bullet points)

        CRITICAL RULES:
        1. Role type alignment is MANDATORY - candidates must have experience in the SAME domain as the role
        2. For technical roles (IT, Engineering, Data):
           - Candidates MUST have technical experience and skills
           - HR/management candidates should NOT be shortlisted unless they have significant technical background
           - Score should be LOW (0-30) for candidates without technical experience
        3. For HR roles:
           - Candidates MUST have HR experience
           - Technical candidates should NOT be shortlisted unless they have significant HR background
           - Score should be LOW (0-30) for candidates without HR experience
        4. For Finance roles:
           - Candidates MUST have finance/accounting experience
           - Score should be LOW (0-30) for candidates without finance experience
        5. NEVER shortlist candidates for roles outside their domain expertise
        6. Consider both domain expertise and required skills when scoring

        Scoring Guidelines:
        - 0-30: No relevant domain experience
        - 31-50: Some relevant experience but significant gaps
        - 51-70: Good match with some minor gaps
        - 71-90: Strong match with minimal gaps
        - 91-100: Exceptional match

        Return ONLY the JSON object with these fields."""

        job_info = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "summary": job.summary,
            "responsibilities": job.responsibilities,
            "requirements": job.requirements,
            "skills": job.skills
        }

        candidate_info = {
            "name": candidate.name,
            "summary": candidate.summary,
            "experience": candidate.experience,
            "education": candidate.education,
            "skills": candidate.skills
        }

        message = anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Job Description:\n{json.dumps(job_info, indent=2)}\n\nCandidate Profile:\n{json.dumps(candidate_info, indent=2)}"
                }
            ]
        )

        if not message.content:
            logger.warning("Empty response from Claude")
            return None

        try:
            # Extract the JSON from the response
            content = message.content[0].text
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                logger.warning("No JSON found in Claude response")
                return None
                
            return json.loads(content[start:end])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            return None

    except Exception as e:
        logger.error(f"Error getting Claude match: {str(e)}")
        return None

async def get_job(job_id: str) -> Optional[Dict]:
    """Get job from database by ID."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if job:
            job["_id"] = str(job["_id"])  # Convert ObjectId to string
        return job
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {str(e)}")
        return None

async def get_candidates(candidate_ids: List[str]) -> List[Dict]:
    """Get candidates from database by IDs."""
    try:
        candidate_ids = [ObjectId(cid) for cid in candidate_ids]
        cursor = db.candidates.find({"_id": {"$in": candidate_ids}})
        candidates = await cursor.to_list(length=None)
        for candidate in candidates:
            candidate["_id"] = str(candidate["_id"])
        return candidates
    except Exception as e:
        logger.error(f"Error getting candidates: {str(e)}")
        return []

async def process_matches(job_id: str, candidate_ids: List[str]) -> Dict:
    """Process matches between a job and candidates using both Python and Claude."""
    try:
        # Get job and candidates from MongoDB
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Convert candidate IDs to ObjectId
        candidate_ids = [ObjectId(cid) for cid in candidate_ids]
        cursor = db.candidates.find({"_id": {"$in": candidate_ids}})
        candidates = await cursor.to_list(length=None)
        
        if not candidates:
            raise HTTPException(status_code=404, detail="No candidates found")
        
        # Convert job info to JobInfo object
        job_info = JobInfo(**job.get('extracted_info', {})) if job.get('extracted_info') else JobInfo()
        
        # Initialize results
        matches = []
        total_candidates = len(candidates)
        processed_candidates = 0
        
        # Process each candidate
        for candidate in candidates:
            try:
                # Convert _id to string
                candidate["_id"] = str(candidate["_id"])
                
                # Get candidate's extracted info
                candidate_info = candidate.get('extracted_info', {})
                if not candidate_info:
                    logger.warning(f"No extracted info for candidate {candidate.get('filename')}")
                    continue
                
                # Convert candidate info to CandidateInfo object
                candidate_info_obj = CandidateInfo(**candidate_info) if candidate_info else CandidateInfo()
                
                # Calculate Python match score
                python_score = calculate_python_score(job_info, candidate_info_obj)
                
                # Only process with Claude if Python score is 50% or above
                claude_score = None
                claude_analysis = None
                if python_score >= 50 and anthropic_client is not None:
                    try:
                        # Get Claude's analysis
                        claude_analysis = get_claude_match(job_info, candidate_info_obj)
                        if claude_analysis:
                            claude_score = claude_analysis.get('match_score')
                    except Exception as e:
                        logger.error(f"Error getting Claude analysis: {str(e)}")
                
                # Determine shortlist status
                shortlist = False
                if claude_score is not None:
                    shortlist = claude_score >= 70
                else:
                    shortlist = python_score >= 70
                
                # Add match to results
                matches.append({
                    'candidate_id': candidate['_id'],
                    'python_score': python_score,
                    'claude_score': claude_score,
                    'claude_analysis': claude_analysis,
                    'shortlist': shortlist
                })
                
                processed_candidates += 1
                logger.info(f"Processed {processed_candidates}/{total_candidates} candidates")
                
            except Exception as e:
                logger.error(f"Error processing candidate {candidate.get('filename')}: {str(e)}")
                continue
        
        # Sort matches by score (best matches first)
        matches.sort(key=lambda x: x['claude_score'] if x['claude_score'] is not None else x['python_score'], reverse=True)
        
        return {
            'job_id': job_id,
            'matches': matches,
            'total_candidates': total_candidates,
            'processed_candidates': processed_candidates
        }
        
    except Exception as e:
        logger.error(f"Error in process_matches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 