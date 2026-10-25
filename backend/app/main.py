"""HTTP entry point for the local KeyRhythm research application."""

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.baseline import (
    FEATURE_MATRIX_VERSION,
    MIN_PROFILES,
    MIN_SAMPLES_PER_PROFILE,
    MODEL_VERSION,
    BaselineModel,
    InsufficientDataError,
    Recording,
    fit_baselines,
    score_sample,
)
from app.baseline_service import load_snapshot
from app.database import Base, BaselineArtifact, Profile, TypingSample, engine, get_db
from app.schemas import (
    ENROLLMENT_TARGET,
    AuthenticationRequest,
    AuthenticationResponse,
    CalibrationResponse,
    ModelProfileStatus,
    ModelStatusResponse,
    ProfileCreate,
    ProfileResponse,
    SampleCreate,
    SampleMetadata,
    SampleResponse,
    SamplesResponse,
    TrainedProfileResponse,
    TrainResponse,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="KeyRhythm API", version="0.3.0", lifespan=lifespan)
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


def calibration_response(model: BaselineModel) -> CalibrationResponse:
    return CalibrationResponse(
        **model.calibration.__dict__, session_disjoint=model.session_disjoint
    )


def current_snapshot(db: Session) -> tuple[list[Recording], str]:
    try:
        return load_snapshot(db)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=409, detail="Stored timing data is invalid"
        ) from exc


@app.post("/api/v1/models/train", response_model=TrainResponse)
def train_baseline(db: DbSession) -> TrainResponse:
    recordings, fingerprint = current_snapshot(db)
    try:
        models = fit_baselines(recordings)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.execute(delete(BaselineArtifact))
    for model in models.values():
        db.add(
            BaselineArtifact(
                profile_id=model.profile_id,
                model_version=MODEL_VERSION,
                dataset_fingerprint=fingerprint,
                state=model.to_json(),
            )
        )
    db.commit()
    all_profile_ids = set(db.scalars(select(Profile.id)))
    return TrainResponse(
        model_version=MODEL_VERSION,
        trained_profiles=[
            TrainedProfileResponse(
                profile_id=model.profile_id,
                training_count=len(model.train_ids),
                validation_count=len(model.validation_ids),
                calibration=calibration_response(model),
            )
            for model in models.values()
        ],
        skipped_profile_ids=sorted(all_profile_ids - models.keys()),
    )


@app.get("/api/v1/models/status", response_model=ModelStatusResponse)
def model_status(db: DbSession) -> ModelStatusResponse:
    recordings, fingerprint = current_snapshot(db)
    counts: dict[int, int] = {}
    for item in recordings:
        counts[item.profile_id] = counts.get(item.profile_id, 0) + 1
    artifacts = {item.profile_id: item for item in db.scalars(select(BaselineArtifact))}
    eligible = sum(count >= MIN_SAMPLES_PER_PROFILE for count in counts.values())
    profiles = []
    for profile_id in db.scalars(select(Profile.id).order_by(Profile.id)):
        count = counts.get(profile_id, 0)
        artifact = artifacts.get(profile_id)
        if count < MIN_SAMPLES_PER_PROFILE:
            profiles.append(
                ModelProfileStatus(
                    profile_id=profile_id, sample_count=count, status="needs_data"
                )
            )
        elif artifact is None:
            profiles.append(
                ModelProfileStatus(
                    profile_id=profile_id, sample_count=count, status="needs_training"
                )
            )
        elif (
            artifact.dataset_fingerprint != fingerprint
            or artifact.model_version != MODEL_VERSION
        ):
            profiles.append(
                ModelProfileStatus(
                    profile_id=profile_id, sample_count=count, status="stale"
                )
            )
        else:
            try:
                model = BaselineModel.from_json(profile_id, artifact.state)
            except (KeyError, TypeError, ValueError):
                profiles.append(
                    ModelProfileStatus(
                        profile_id=profile_id, sample_count=count, status="stale"
                    )
                )
            else:
                profiles.append(
                    ModelProfileStatus(
                        profile_id=profile_id,
                        sample_count=count,
                        status="ready",
                        training_count=len(model.train_ids),
                        validation_count=len(model.validation_ids),
                        calibration=calibration_response(model),
                    )
                )
    return ModelStatusResponse(
        model_version=MODEL_VERSION,
        minimum_samples_per_profile=MIN_SAMPLES_PER_PROFILE,
        minimum_profiles=MIN_PROFILES,
        eligible_profile_count=eligible,
        profiles=profiles,
    )


@app.post("/api/v1/authenticate", response_model=AuthenticationResponse)
def authenticate(
    payload: AuthenticationRequest, db: DbSession
) -> AuthenticationResponse:
    existing_profile(payload.profile_id, db)
    artifact = db.get(BaselineArtifact, payload.profile_id)
    if artifact is None:
        raise HTTPException(
            status_code=409, detail="Train the baseline before verification"
        )
    _, fingerprint = current_snapshot(db)
    if (
        artifact.dataset_fingerprint != fingerprint
        or artifact.model_version != MODEL_VERSION
    ):
        raise HTTPException(
            status_code=409, detail="Enrollment data changed; retrain the baseline"
        )
    try:
        model = BaselineModel.from_json(payload.profile_id, artifact.state)
        score, distance, accepted = score_sample(model, payload.sample.timing_sequence)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409, detail="Stored baseline is invalid; retrain it"
        ) from exc
    threshold = 1 / (1 + model.threshold_distance)
    return AuthenticationResponse(
        profile_id=payload.profile_id,
        similarity_score=score,
        decision_threshold=threshold,
        distance=distance,
        accepted=accepted,
        model_version=MODEL_VERSION,
        feature_matrix_version=FEATURE_MATRIX_VERSION,
        calibration=calibration_response(model),
        explanation=(
            "Normalized typing timing is within the validation-calibrated baseline threshold."
            if accepted
            else "Normalized typing timing exceeds the validation-calibrated baseline threshold."
        ),
    )
