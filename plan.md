# KeyRhythm
## Product Requirements Document (PRD)

**Project type:** Neural Computation and Applications — University Mini-Project  
**Version:** 1.0  
**Development approach:** Incremental, milestone-based implementation using Codex  
**Category:** Neural networks, behavioural biometrics, sequence learning, cybersecurity

---

## 1. Project Overview

### 1.1 Project title

**KeyRhythm: Continuous User Authentication Using Siamese Neural Networks and Keystroke Dynamics**

### 1.2 Problem statement

Traditional authentication systems primarily verify a user's identity at login. Once a user has logged in, the system generally assumes that the same person continues to use the device.

However, typing behaviour varies between individuals. People develop characteristic patterns involving key-hold durations, intervals between successive keystrokes, pauses, and typing rhythm.

KeyRhythm investigates whether these temporal patterns can be learned by neural networks and used to verify a user's identity.

The system will collect timing information from controlled typing exercises, learn representations of typing behaviour, and estimate whether a new typing sample resembles a previously enrolled user's samples.

### 1.3 Proposed solution

Build a web application that allows users to:

1. Enrol a typing profile by completing repeated typing exercises.
2. Extract temporal features from their keystroke patterns.
3. Train and compare conventional machine-learning and neural-network approaches.
4. Authenticate by typing the same challenge again.
5. Receive a similarity score and an authentication decision.
6. Explore model performance through an experimental dashboard.

The primary neural model will be a **Siamese neural network** trained to determine whether two typing samples belong to the same user.

### 1.4 Core research question

Can a Siamese neural network learn discriminative representations of typing behaviour that distinguish genuine users from impostors, and how does it compare with a conventional statistical or machine-learning baseline?

---

## 2. Objectives

### Primary objectives

- Implement a complete behavioural authentication pipeline.
- Collect and process keystroke timing data.
- Develop a conventional baseline before implementing the neural model.
- Train a Siamese network using genuine and impostor sample pairs.
- Evaluate performance using biometric verification metrics.
- Present authentication results and experimental findings in an interactive interface.

### Secondary objectives

- Visualise typing rhythm and temporal features.
- Compare performance with different amounts of enrolment data.
- Investigate the effect of typing variability and sample length.
- Document limitations, false acceptances, and false rejections.
- Produce reproducible experiments suitable for an academic report.

### Success criteria

The project is considered successful when:

1. A user can enrol and submit new typing samples through the application.
2. The backend can extract features and persist timing-only samples.
3. A baseline model and a Siamese model can both be evaluated.
4. Genuine and impostor verification trials can be performed.
5. FAR, FRR, EER, ROC-AUC, and the confusion matrix can be reported where applicable.
6. The user can inspect results without manually running Python scripts.
7. All major functionality has automated tests and documented setup instructions.

---

## 3. Target Users

### Primary user: Student researcher

A student investigating neural computation, sequence modelling, biometric verification, and model evaluation.

### Secondary user: Demonstration participant

A participant who enrols a typing profile and tests how consistently the system recognises their typing behaviour.

### Administrator/researcher

A user who manages experimental datasets, trains models, selects evaluation configurations, and reviews results.

The initial version is intended for academic experimentation, not production-grade identity security.

---

## 4. Scope

### 4.1 Included in the initial project

- Local web application.
- User/profile creation.
- Fixed-text typing challenge.
- Keystroke timing collection.
- Feature extraction and preprocessing.
- Enrolment sample storage.
- Statistical or conventional ML baseline.
- Siamese neural network.
- Pair-based model training and verification.
- Authentication score and threshold-based decision.
- Evaluation dashboard.
- Experiment results and plots.
- Unit tests, integration tests, and documentation.

### 4.2 Explicitly excluded from the initial project

- Operating-system-wide keylogging.
- Capturing typing from other websites or applications.
- Recording passwords or arbitrary text entered by users.
- Webcam, microphone, or other biometric collection.
- Production account security or banking-grade authentication.
- Cloud deployment and multi-device synchronisation.
- Complex enterprise authentication integrations.
- Unnecessary microservices or distributed infrastructure.

These exclusions keep the project focused on neural computation rather than unrelated infrastructure.

---

## 5. Technology Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Recharts for analytical visualisations

### Backend

- Python 3.11 or another compatible version supported by the chosen dependencies
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite

### Machine learning

- PyTorch
- NumPy
- pandas
- scikit-learn
- Matplotlib
- scikit-learn metrics for ROC and verification evaluation

### Testing and development

- pytest
- Vitest
- React Testing Library
- Ruff for Python linting
- Git for version control

Use stable, mutually compatible dependency versions. Do not introduce additional frameworks unless there is a clear technical requirement.

---

## 6. System Architecture

The application will follow a simple frontend/backend architecture with a dedicated machine-learning module.

### Component responsibilities

**Frontend**
- Profile creation.
- Typing challenge presentation.
- Client-side timing capture.
- Authentication result presentation.
- Experiment and model-performance visualisations.

**FastAPI backend**
- Profile and sample management.
- Input validation.
- Feature-processing orchestration.
- Model training and inference endpoints.
- Experiment result retrieval.

**Machine-learning module**
- Feature extraction and normalisation.
- Baseline model training.
- Siamese encoder architecture.
- Pair generation and contrastive learning.
- Similarity scoring.
- Threshold calibration.
- Evaluation metrics.

**SQLite**
- User profile metadata.
- Timing-only sample data.
- Model and experiment metadata.
- Authentication trial results.

Keep model logic independent of the HTTP routes so it can be tested and executed directly from Python.

### Expected data flow

1. A user selects a profile.
2. The frontend displays the fixed typing challenge.
3. Timing events are collected locally in the browser.
4. The frontend validates that the challenge was completed correctly.
5. Only timing features or timing sequences are submitted to the backend.
6. The backend validates and stores the sample.
7. The verification pipeline compares the new sample against the enrolled profile.
8. The system returns a score, decision, and explanatory summary.
9. The dashboard displays results and evaluation statistics.

---

## 7. Functional Requirements

### FR-01: Profile management

Users must be able to create a profile, view its enrolment status, and delete it.

Profiles should have an internal identifier and a display label. Avoid collecting unnecessary personal information.

### FR-02: Typing challenge

Display one fixed sentence consistently across enrolment and verification.

The user must type the challenge directly into the designated input field.

The initial implementation must not record typing outside this field.

### FR-03: Timing collection

Collect the following timing information where technically valid:

- Key-hold duration.
- Inter-key interval.
- Key-down-to-key-down interval.
- Long-pause indicators.
- Overall typing duration.
- Derived statistics such as mean, standard deviation, median, and selected percentiles.

Use consistent units, preferably milliseconds internally or seconds with a clearly documented convention.

Ignore modifier-key events where appropriate, repeated key-down events, and invalid or incomplete timing sequences.

### FR-04: Sample validation

Reject samples that are incomplete or structurally invalid.

Validate:
- Challenge completion.
- Timing-array lengths.
- Missing values.
- Non-finite values.
- Invalid or negative durations.
- Minimum usable sequence length.

A mistyped or corrected challenge should not silently produce a misaligned feature sequence. Implement a clear restart or sample-retry flow.

### FR-05: Enrolment

Allow multiple samples to be collected for one profile.

Use a configurable initial target of 10 enrolment samples. The UI should indicate progress and allow a user to restart an invalid sample.

The number of samples required for meaningful model training must be configurable and documented separately from the UI default.

### FR-06: Authentication

The user submits a fresh typing sample.

The backend compares it with the selected profile's enrolment data and returns:

- Similarity score.
- Authentication decision.
- Decision threshold.
- Model version.
- Basic explanation of the result.

The result must be based on actual model inference, not a hardcoded or randomly generated score.

### FR-07: Model experimentation

The researcher must be able to train, evaluate, and compare the baseline and Siamese model.

Record model configuration, dataset version, training parameters, and evaluation metrics.

### FR-08: Experiment dashboard

Display:

- Number of enrolled profiles.
- Number of collected samples.
- Model training status.
- Baseline versus Siamese performance.
- FAR and FRR.
- EER where estimable.
- ROC curve and AUC.
- Confusion matrix.
- Authentication trial history.
- Training loss history.

Do not display metrics that cannot be calculated reliably from the available data.

---

## 8. Neural Computation Design

### 8.1 Feature representation

Represent each valid typing sample as a fixed-length sequence:

`X ∈ R^(T × F)`

Where:
- `T` is the number of aligned typing positions.
- `F` is the number of temporal features per position.

The initial feature channels should include:

1. Key-hold duration.
2. Inter-key timing.
3. A pause or timing-deviation feature.

The exact representation should be documented and tested. Use the same preprocessing pipeline during training and inference.

Do not include the literal typed text as a model feature.

### 8.2 Baseline model

Implement a baseline before the Siamese model.

Use a conventional distance-based verifier or a one-class model trained on enrolment samples. A robust standardised-distance baseline is acceptable as the first implementation.

Evaluate it using the same verification protocol intended for the neural model.

The baseline exists to answer an important question: does the neural architecture actually improve on a simpler method?

### 8.3 Siamese neural network

Implement two branches that share the same encoder weights.

Each branch receives a typing sample and produces an embedding vector.

The network compares the two embeddings and learns whether the samples belong to the same user.

Recommended initial architecture:

- Input: fixed-length temporal feature sequence.
- Encoder: small one-dimensional CNN.
- Temporal pooling.
- Dense projection layer.
- Embedding dimension: configurable, initially 32.
- Similarity: cosine similarity or Euclidean distance.
- Training objective: contrastive loss.

The network must support variable experiment configurations without requiring a redesign of the application.

### 8.4 Pair construction

Generate:

- Positive pairs: two samples belonging to the same user.
- Negative pairs: samples belonging to different users.

Balance or appropriately weight positive and negative examples.

Prevent data leakage: split original samples into training, validation, and test sets before constructing pairs. Samples from the same recording must not appear in both training and test sets.

### 8.5 Authentication decision

Calibrate the decision threshold using validation data.

Do not choose a threshold based on the final test set.

For a distance-based verifier, a smaller distance should indicate greater similarity. For a similarity-based verifier, a larger score should indicate greater similarity.

Keep the score direction and threshold convention consistent throughout the application.

---

## 9. Dataset and Experimental Methodology

### Initial data collection

Collect samples from multiple consenting participants.

A useful preliminary target is 10 or more participants with approximately 20–30 valid samples per participant, if practical. This is an experimental target, not a guarantee of sufficient data or reliable performance.

The live demonstration can operate with fewer samples, but the project must clearly distinguish a functional demonstration from a statistically credible evaluation.

### Optional public benchmark

In a later milestone, add an adapter for a public keystroke-dynamics dataset, such as the CMU benchmark.

Check its format, permitted use, and licensing before integration. Do not assume that its feature schema is identical to the live typing challenge schema.

### Data splitting

Split by original samples and, where possible, by collection session.

Use:
- Training set for model fitting.
- Validation set for model selection and threshold calibration.
- Held-out test set for final performance reporting.

Where the dataset supports it, report both known-user verification and generalisation to previously unseen users as separate experiments. These are different evaluation problems.

### Required metrics

**False Acceptance Rate (FAR)**  
The proportion of impostor attempts incorrectly accepted.

**False Rejection Rate (FRR)**  
The proportion of genuine attempts incorrectly rejected.

**Equal Error Rate (EER)**  
The error rate at the operating point where FAR and FRR are approximately equal, when such a point can be estimated.

**ROC-AUC**  
The area under the receiver operating characteristic curve.

Also report:
- Precision and recall where meaningful.
- Confusion matrix.
- Sample count and number of participants.
- Threshold used.
- Test protocol and limitations.

Never claim that a small dataset demonstrates production-grade security.

---

## 10. Privacy and Security Requirements

Privacy is a core product requirement.

- Collect timing information only inside the designated typing field.
- Do not implement a global keyboard listener.
- Do not send or persist the actual challenge text or arbitrary typed content.
- Process transient keyboard events in the browser and discard raw events after deriving the timing sequence.
- Do not persist key values, characters, passwords, or raw keyboard-event logs.
- Store only the timing sequences and derived features required for the experiment.
- Provide profile deletion.
- Explain that timing patterns are behavioural biometric data.
- Obtain participant consent before collecting samples.
- Keep the default setup local.
- Avoid sending samples to third-party services.
- Do not describe the system as a secure replacement for passwords or multifactor authentication.

A production system would need substantially stronger threat modelling, liveness protections, privacy controls, and security evaluation.

---

## 11. User Interface Requirements

The application should have a clean, light-themed research dashboard with a professional technical aesthetic.

### Page A: Overview

Show:
- Project name and description.
- Total profiles and samples.
- Active model and training status.
- Latest evaluation summary.
- Quick actions for enrolment and authentication.

### Page B: Enrolment

Show:
- Selected profile.
- Fixed challenge sentence.
- Typing input.
- Sample progress, such as 4/10.
- Validation feedback.
- Restart and continue controls.

### Page C: Authentication

Show:
- Profile selection.
- Typing challenge.
- Verification progress.
- Similarity or distance score.
- Accepted/rejected decision.
- Clear explanation that this is an experimental result.

### Page D: Model Laboratory

Show:
- Model selection.
- Training parameters.
- Train and evaluate controls.
- Training loss chart.
- Baseline versus neural-model comparison.
- Current model version.

### Page E: Evaluation

Show:
- FAR and FRR.
- EER and ROC-AUC where estimable.
- ROC curve.
- Confusion matrix.
- Sample counts.
- Experiment configuration.
- Limitations and dataset split information.

All charts must be based on actual backend results.

---

## 12. API Requirements

Use versioned endpoints under `/api/v1`.

Suggested initial API surface:

- `GET /api/v1/health` — backend health.
- `GET /api/v1/profiles` — list profiles.
- `POST /api/v1/profiles` — create a profile.
- `DELETE /api/v1/profiles/{profile_id}` — delete a profile and its associated data.
- `POST /api/v1/profiles/{profile_id}/samples` — submit a validated timing sample.
- `GET /api/v1/profiles/{profile_id}/samples` — retrieve sample counts and permitted metadata.
- `POST /api/v1/models/train` — initiate training.
- `GET /api/v1/models/status` — retrieve model status.
- `POST /api/v1/authenticate` — verify a timing sample against a profile.
- `POST /api/v1/experiments/evaluate` — evaluate a selected model.
- `GET /api/v1/experiments` — list experiments.
- `GET /api/v1/experiments/{experiment_id}` — retrieve experiment details.

The API schema must use explicit request and response models.

Do not return raw biometric data in list endpoints unless the operation specifically requires it.

Training may run synchronously for small datasets initially. If training becomes slow, introduce a background job mechanism in a later milestone rather than prematurely adding infrastructure.

---

## 13. Data Model

### Profile

- `id`
- `display_name`
- `created_at`
- `enrollment_status`

### TypingSample

- `id`
- `profile_id`
- `created_at`
- `challenge_version`
- `timing_sequence`
- `feature_version`
- `is_valid`

Store the timing sequence as structured numeric data using a documented serialization format.

### ModelArtifact

- `id`
- `model_type`
- `model_version`
- `created_at`
- `configuration`
- `artifact_path`
- `dataset_version`

### Experiment

- `id`
- `model_id`
- `created_at`
- `split_configuration`
- `training_configuration`
- `metrics`
- `threshold`
- `notes`

### AuthenticationTrial

- `id`
- `profile_id`
- `model_id`
- `created_at`
- `score`
- `threshold`
- `decision`

Avoid storing raw keyboard events or the typed sentence in these tables.

---

## 14. Development Milestones

**Important:** Implement these milestones in order. Do not ask Codex to build the entire application in one request.

### Milestone 0 — Repository inspection and project plan

**Goal:** Establish the development environment and a clear implementation plan.

Tasks:
- Inspect the repository before changing files.
- Identify existing code, dependencies, and configuration.
- Create a concise implementation plan based on this PRD.
- Establish frontend and backend project structure.
- Configure Git-friendly ignore rules and environment configuration.
- Add a README with setup instructions.

Acceptance criteria:
- The project structure is documented.
- Frontend and backend dependencies are defined.
- Setup commands are reproducible.
- No application features are implemented prematurely.

### Milestone 1 — Application foundation

**Goal:** Build a working frontend and backend shell.

Tasks:
- Set up React, TypeScript, and Vite.
- Set up FastAPI.
- Add the health endpoint.
- Configure local frontend-to-backend communication.
- Create the initial navigation and dashboard layout.
- Add basic frontend and backend tests.

Acceptance criteria:
- Frontend starts successfully.
- Backend starts successfully.
- Health endpoint returns a successful response.
- Frontend can display backend connectivity status.
- Tests pass.

Do not implement neural networks in this milestone.

### Milestone 2 — Typing capture and enrolment

**Goal:** Build a reliable, privacy-conscious data-collection pipeline.

Tasks:
- Implement profile creation and listing.
- Build the fixed typing challenge.
- Capture key timing events inside the designated input.
- Derive aligned timing sequences in the browser.
- Validate sample structure and challenge completion.
- Implement sample persistence with SQLite.
- Add profile deletion.
- Add tests for invalid sequences and privacy constraints.

Acceptance criteria:
- Users can create profiles.
- Users can submit valid samples.
- Sample counts update correctly.
- Incomplete or invalid samples are rejected.
- Typed text and raw key values are not transmitted or persisted.
- Deleting a profile removes its associated data.

Use a temporary, documented collection target until model experiments determine whether more samples are required.

### Milestone 3 — Feature engineering and baseline verifier

**Goal:** Establish a working, measurable authentication baseline.

Tasks:
- Implement feature extraction in a reusable Python module.
- Add normalization and validation.
- Define the training and evaluation data structures.
- Implement a simple distance-based or one-class baseline.
- Add threshold calibration using validation samples.
- Implement initial authentication inference.
- Add tests for consistent preprocessing.

Acceptance criteria:
- The same input produces consistent features.
- Invalid numeric values are rejected.
- A sample can be compared with an enrolled profile.
- A score and threshold-based decision are returned.
- Baseline evaluation metrics can be generated.
- The frontend can display an actual baseline result.

Do not implement the Siamese network until this pipeline works.

### Milestone 4 — Siamese neural network

**Goal:** Implement and train the primary neural model.

Tasks:
- Build the shared-weight encoder in PyTorch.
- Implement positive and negative pair generation.
- Implement contrastive loss.
- Create a reproducible training loop.
- Add validation monitoring and checkpoint saving.
- Implement embedding extraction and similarity scoring.
- Calibrate the authentication threshold on validation data.
- Add unit tests for shapes, pair labels, and inference.

Acceptance criteria:
- The model trains on a valid dataset.
- Training loss and validation results are recorded.
- Checkpoints can be loaded for inference.
- Preprocessing is identical between training and inference.
- Data leakage checks are in place.
- The model returns a real similarity score.
- A failed or incomplete training run is reported clearly.

If available data is too small for meaningful learning, report that limitation instead of manufacturing successful results.

### Milestone 5 — Model comparison and evaluation

**Goal:** Turn the implementation into a credible academic experiment.

Tasks:
- Implement the final evaluation pipeline.
- Compare the baseline and Siamese model.
- Calculate FAR, FRR, ROC-AUC, and EER where appropriate.
- Generate ROC curves and confusion matrices.
- Evaluate the effect of enrolment sample count.
- Record model configuration and dataset split.
- Add a repeatable experiment command.

Acceptance criteria:
- Both models are evaluated using the same held-out test samples.
- Thresholds are chosen without looking at the test labels.
- Results include denominators and dataset sizes.
- Plots are generated from actual evaluation results.
- Metrics and experiment settings are saved.
- The results can be reproduced from documented commands.

If the sample size does not support a trustworthy EER or other metric, explain why and omit the unsupported claim.

### Milestone 6 — Complete dashboard integration

**Goal:** Connect all working components into a coherent application.

Tasks:
- Complete the overview dashboard.
- Finish the enrolment and authentication flows.
- Build the model laboratory.
- Add training status and experiment history.
- Visualise model comparisons and metrics.
- Add clear loading, empty, error, and success states.
- Ensure the interface remains usable on common desktop screen sizes.

Acceptance criteria:
- Users can complete the end-to-end workflow through the UI.
- The UI reflects actual backend state.
- Training and inference errors are understandable.
- No scores or charts are hardcoded.
- Existing tests continue to pass.

### Milestone 7 — Final testing, documentation, and academic deliverables

**Goal:** Prepare a demonstrable and defensible university submission.

Tasks:
- Run the complete test suite.
- Test fresh installation from the README.
- Verify profile deletion and data-retention behaviour.
- Check preprocessing consistency and model reproducibility.
- Document the architecture and neural computation.
- Prepare final experiment tables and figures.
- Write limitations and future-work sections.
- Add a demonstration script and screenshots.

Acceptance criteria:
- A new developer can set up the project using the documentation.
- The demo works from start to finish.
- Model results can be reproduced.
- Privacy behaviour has been tested.
- The final report distinguishes measured results from hypotheses.
- Known limitations are documented.

### Optional Milestone 8 — Public benchmark and advanced experiments

Only begin after Milestone 7 is complete.

Possible additions:
- Public keystroke-dynamics benchmark adapter.
- Subject-independent evaluation.
- Comparison of MLP, CNN, and Siamese architectures.
- Ablation study of temporal features.
- Calibration and robustness analysis.
- Docker-based deployment.

Do not let optional work delay a complete, tested mini-project.

---

## 15. Non-Functional Requirements

### Reliability
- Validate all API inputs.
- Handle empty datasets and missing model artifacts.
- Provide meaningful error responses.
- Avoid silent fallback to fabricated predictions.

### Maintainability
- Keep API routes, data access, feature extraction, model code, and evaluation separate.
- Use type annotations.
- Document public interfaces.
- Avoid unnecessary abstraction.

### Reproducibility
- Fix random seeds where appropriate.
- Save experiment configurations.
- Record dataset splits.
- Version feature preprocessing and model artifacts.
- Document dependency versions.

### Privacy
- Collect timing data only with user consent.
- Never persist typed text or raw keyboard-event logs.
- Provide profile and sample deletion.
- Keep the default setup local.

### Performance
- Keep the initial dataset and models small enough for a typical student laptop.
- Avoid requiring a GPU.
- Keep the UI responsive during inference.
- Add background training only if needed.

---

## 16. Risks and Mitigations

**Risk: Insufficient training data.**  
Mitigation: Start with a small working baseline, collect more participants when possible, and distinguish demonstration results from reliable evaluation.

**Risk: Model overfitting.**  
Mitigation: Split by original sample and session before pair generation, use validation data, and report held-out results.

**Risk: Similarity scores are mistaken for probabilities.**  
Mitigation: Label similarity separately from calibrated acceptance confidence. Do not call an uncalibrated cosine score a probability.

**Risk: Inconsistent typing sequences.**  
Mitigation: Fix the challenge text, version the challenge, validate alignment, and reject invalid sequences.

**Risk: Neural model performs worse than the baseline.**  
Mitigation: Treat this as a legitimate research result. Analyse data quantity, feature quality, and generalisation rather than fabricating improvement.

**Risk: Scope becomes too large.**  
Mitigation: Follow the milestone order, defer optional work, and require passing acceptance tests before proceeding.

**Risk: Privacy leakage.**  
Mitigation: Do not transmit typed content, avoid global keyboard monitoring, and provide explicit deletion controls.

---

## 17. Final Deliverables

The completed submission should contain:

1. Working web application.
2. Backend API and database.
3. Timing-feature extraction pipeline.
4. Baseline verification model.
5. Siamese neural network implementation.
6. Reproducible training and evaluation scripts.
7. Saved model artifacts and experiment metadata.
8. Performance tables and plots.
9. Automated tests.
10. README and architecture documentation.
11. Final university report.
12. Demonstration walkthrough.

The academic report should explain the neural architecture, loss function, feature representation, data-splitting protocol, threshold calibration, evaluation metrics, and observed limitations.

---

## 18. Definition of Done

KeyRhythm is complete when a user can enrol a profile, submit a new typing sample, receive a model-generated verification decision, and inspect a reproducible comparison between a conventional baseline and the Siamese neural network.

The system must demonstrate real neural computation, measurable evaluation, and responsible data collection.

A working interface alone is not sufficient: the trained model, evaluation methodology, and documented experimental findings are essential parts of the project.
