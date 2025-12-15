from typing import Optional
from fastapi import APIRouter, HTTPException

from app.models import (
    QueryRequest,
    QueryResponse,
    LensPreviewRequest,
    LensPreviewResponse,
    CalendarContextUnavailable,
)
from app.services.time_context import get_time_context
from app.services.calendar_context import get_calendar_context
from app.services.role_guess import get_role_guess
from app.services.lens_assembly import assemble_lens, lens_to_yaml
from app.services.drift_guard import detect_drift, get_regeneration_prompt_modifier
from app.services.llm_client import llm_client


router = APIRouter()


# IMMUTABLE prompt template from spec section 6.2
PRIMARY_SYSTEM_PROMPT = """You are a helpful assistant.
The following YAML describes the user's current situation and role.
Use it to adapt tone, depth, and framing.
Do not mention the YAML explicitly.

<user_context>
{lens_yaml}
</user_context>"""


async def _gather_context(calendar_token: Optional[str]):
    """
    Gather all context following the runtime flow from spec section 2.1:
    1. Time Context (local, sync)
    2. Calendar Context (LLM micro-call)
    3. Role Guess is handled separately as it needs the query
    """
    # Step 1: Time Context (local, deterministic)
    time_context = get_time_context()

    # Step 2: Calendar Context (LLM micro-call)
    calendar_context = await get_calendar_context(calendar_token)

    return time_context, calendar_context


async def _generate_response(
    query: str,
    lens_yaml: str,
    modifier: Optional[str] = None,
) -> str:
    """Generate response from primary LLM."""
    system_prompt = PRIMARY_SYSTEM_PROMPT.format(lens_yaml=lens_yaml)

    # Add modifier if provided (for regeneration)
    if modifier:
        system_prompt += f"\n\nAdditional instruction: {modifier}"

    return await llm_client.primary_call(
        system_prompt=system_prompt,
        user_prompt=query,
    )


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main query endpoint.

    Runtime flow (spec section 2.1):
    1. Time Context (local, sync)
    2. Calendar Context (LLM micro-call)
    3. Role Guess (LLM micro-call)
    4. Lens Assembly (deterministic)
    5. Primary LLM Call
    6. Drift Guard (post-generation)
    7. Final Response
    """
    try:
        # Steps 1-2: Gather time and calendar context
        time_context, calendar_context = await _gather_context(request.calendar_token)

        # Step 3: Role Guess (LLM micro-call)
        role_guess = await get_role_guess(
            query=request.query,
            time_context=time_context,
            calendar_context=calendar_context,
        )

        # Step 4: Lens Assembly (deterministic)
        lens = assemble_lens(
            time_context=time_context,
            calendar_context=calendar_context,
            role_guess=role_guess,
        )

        lens_yaml = lens_to_yaml(lens)

        # Step 5: Primary LLM Call
        response = await _generate_response(request.query, lens_yaml)

        # Step 6: Drift Guard (post-generation)
        drift_result = detect_drift(response, lens)

        regenerated = False
        warning = None

        if drift_result.drift_detected:
            # Per spec section 7.2: Maximum 1 regeneration
            modifier = get_regeneration_prompt_modifier(drift_result)
            regenerated_response = await _generate_response(
                request.query, lens_yaml, modifier
            )

            # Check second attempt
            second_drift = detect_drift(regenerated_response, lens)

            if second_drift.drift_detected:
                # Per spec: If second attempt fails, return response with warning flag
                response = regenerated_response
                warning = f"Response may contain {second_drift.drift_type}"
            else:
                response = regenerated_response

            regenerated = True

        # Step 7: Final Response
        return QueryResponse(
            response=response,
            lens=lens,
            regenerated=regenerated,
            model=llm_client.get_model_name(),
            warning=warning,
        )

    except Exception as e:
        # Per spec section 9: Primary LLM fails -> Return error to user
        # Lens assembly fails -> Abort request
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lens/preview", response_model=LensPreviewResponse)
async def lens_preview(request: LensPreviewRequest):
    """
    Lens preview endpoint for transparency.

    Shows what lens would be assembled for a given query
    without making the primary LLM call.
    """
    try:
        # Gather time and calendar context
        time_context, calendar_context = await _gather_context(request.calendar_token)

        # Get role guess
        role_guess = await get_role_guess(
            query=request.query,
            time_context=time_context,
            calendar_context=calendar_context,
        )

        # Assemble lens
        lens = assemble_lens(
            time_context=time_context,
            calendar_context=calendar_context,
            role_guess=role_guess,
        )

        return LensPreviewResponse(
            lens=lens,
            sources_used=lens.sources_used,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
