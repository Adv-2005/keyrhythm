"""HTTP entry point for the local KeyRhythm research application."""

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.database import Base, Profile, TypingSample, engine, get_db
from app.schemas import (
    ENROLLMENT_TARGET,
    ProfileCreate,
    ProfileResponse,
    SampleCreate,
    SampleMetadata,
    SampleResponse,
    SamplesResponse,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="KeyRhythm API", version="0.2.0", lifespan=lifespan)
DbSession = Annotated[Session, Depends(get_db)]


@app.exception_handler(RequestValidationError)
async def invalid_request(
    _request: Request, _error: RequestValidationError
) -> JSONResponse:
    # Pydantic's default error response includes rejected input values.
    return JSONResponse(status_code=422, content={"detail": "Invalid request payload"})


def profile_response(profile: Profile, count: int) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        display_name=profile.display_name,
        created_at=profile.created_at,
        sample_count=count,
        enrollment_status="ready" if count >= ENROLLMENT_TARGET else "collecting",
    )


def existing_profile(profile_id: int, db: Session) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report whether the API is available."""
    return HealthResponse(status="ok")


@app.get("/api/v1/profiles", response_model=list[ProfileResponse])
def list_profiles(db: DbSession) -> list[ProfileResponse]:
    counts = dict(
        db.execute(
            select(TypingSample.profile_id, func.count(TypingSample.id)).group_by(
                TypingSample.profile_id
            )
        ).all()
    )
    return [
        profile_response(profile, counts.get(profile.id, 0))
        for profile in db.scalars(select(Profile).order_by(Profile.id))
    ]


@app.post(
    "/api/v1/profiles",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(payload: ProfileCreate, db: DbSession) -> ProfileResponse:
    profile = Profile(display_name=payload.display_name)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile_response(profile, 0)


@app.delete("/api/v1/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, db: DbSession) -> None:
    profile = existing_profile(profile_id, db)
    db.delete(profile)
    db.commit()


@app.post(
    "/api/v1/profiles/{profile_id}/samples",
    response_model=SampleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sample(
    profile_id: int, payload: SampleCreate, db: DbSession
) -> SampleResponse:
    existing_profile(profile_id, db)
    sample = TypingSample(
        profile_id=profile_id,
        session_id=str(payload.session_id),
        challenge_version=payload.challenge_version,
        feature_version=payload.feature_version,
        timing_sequence=payload.timing_sequence.model_dump(),
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    count = (
        db.scalar(
            select(func.count(TypingSample.id)).where(
                TypingSample.profile_id == profile_id
            )
        )
        or 0
    )
    return SampleResponse(
        id=sample.id,
        profile_id=profile_id,
        created_at=sample.created_at,
        sample_count=count,
    )


@app.get("/api/v1/profiles/{profile_id}/samples", response_model=SamplesResponse)
def list_samples(profile_id: int, db: DbSession) -> SamplesResponse:
    existing_profile(profile_id, db)
    samples = db.scalars(
        select(TypingSample)
        .where(TypingSample.profile_id == profile_id)
        .order_by(TypingSample.id)
    ).all()
    return SamplesResponse(
        profile_id=profile_id,
        sample_count=len(samples),
        samples=[
            SampleMetadata(
                id=s.id,
                created_at=s.created_at,
                session_id=s.session_id,
                challenge_version=s.challenge_version,
                feature_version=s.feature_version,
            )
            for s in samples
        ],
    )
