# Architecture and neural computation

KeyRhythm is a local research prototype. The browser captures timing for one fixed challenge inside a focused input; FastAPI validates numeric sequences, SQLite stores consented enrolment samples, and model modules operate on versioned timing features. The frontend and API communicate through Vite's local `/api` proxy during development. No typed characters are sent to the backend.

```text
Focused challenge input → timing capture → FastAPI validation → SQLite samples
                                                ↓
                                   versioned 44 × 3 features
                                      ↙                ↘
                          distance baseline      Siamese CNN
                                      ↘                ↙
                           saved known-user comparison
                                      ↓
                             dashboard / report export
```

## Data and lifecycle

- `frontend/src/` holds the focused capture component and live views. `backend/app/main.py` owns HTTP routes and data deletion. `schemas.py` checks the challenge, versions, array lengths, finite values, and timing arithmetic.
- `database.py` stores profiles, numeric timing sequences with collection session IDs, baseline states, one neural artifact record, saved experiments, and verification summaries. Neural weights live in a local checkpoint file. `KEYRHYTHM_DATABASE_URL` and `KEYRHYTHM_ARTIFACT_DIR` isolate these two stores.
- Fresh authentication timing is used for inference and discarded. The retained trial contains profile, model, score, threshold, decision, and time, without the timing sequence. Enrolment timing remains sensitive biometric data even when profile labels are pseudonyms.
- Deleting a profile cascades its samples, baseline artifact, and trial summaries. It also removes the global neural checkpoint and all experiments because both may depend on that profile. Copies of the database, downloaded plots, and exported reports are outside this deletion transaction and must be managed separately.

## Capture and features

The `fixed-1` challenge has 44 positions. The browser records monotonic `keydown` and `keyup` event timestamps, rejecting paste, correction, repeated keys, composition input, focus loss, and unfinished releases. At each position, `hold_ms` is key-up minus key-down. Adjacent positions have `down_down_ms` and `flight_ms` (next down minus current up); negative flight is valid for overlapping holds. `long_pauses` flags flights of at least 750 ms. The server validates the numeric schema but cannot independently prove what text an untrusted client typed.

`baseline-features-v1` maps each position to `[hold_ms, down_down_ms, long_pause_flag]`, with zero interval and pause padding in the last row. The resulting matrix is 44 × 3. The shared robust scaler uses the median and median absolute deviation of training recordings only, with floors of 20 ms for holds and 30 ms for intervals. The pause channel has center zero and scale one. Both training and inference call the same feature extraction and normalization functions. The neural path additionally clips normalized values to `[-10, 10]` and transposes the matrix to `[3, 44]`; this operation is shared by training and inference through `tensor_for()`.

## Baseline and Siamese verifier

The distance baseline forms a per-profile median prototype from training matrices. It computes root-mean-square distance from a candidate to that prototype and displays similarity `1 / (1 + distance)`. Validation genuine and other-profile attempts select a profile threshold that minimizes balanced false acceptance and false rejection. The score is a monotonic similarity, not a calibrated probability.

The `siamese-cnn-v1` encoder takes a `[3, 44]` tensor. Its shared branch is `Conv1d(3, 16, kernel=5, padding=2) → ReLU → Conv1d(16, 32, kernel=5, padding=2) → ReLU → adaptive average pool to 4 positions → flatten 128 → linear embedding` (32 dimensions by default), followed by unit-length normalization. A positive pair contains two recordings from one profile; a negative pair contains recordings from different profiles. Pair lists are balanced and seeded within each partition. For embedding distance `d`, pair label `y=1` for same profile, and margin `m`, the batch mean contrastive loss is `y·d² + (1−y)·max(0,m−d)²`. Adam trains the shared encoder; the best checkpoint is chosen by validation pair loss.

Each profile reference is the unit-normalized mean of its training embeddings. Validation attempts determine a distance threshold; inference compares a new embedding to the claimed profile reference. The displayed similarity is `1 / (1 + distance)` and acceptance uses strict `similarity > threshold`. Training seeds Python pair sampling and PyTorch initialization. The checkpoint stores weights; SQLite stores the scaler, reference embeddings, settings, split IDs, version strings, loss history, and dataset fingerprint.

## Evaluation and leakage controls

Neural training needs three profiles with at least ten recordings each as a software gate. It splits original recordings into train, validation, and test before fitting the scaler or constructing pairs. When enough collection sessions exist, entire sessions are separated; otherwise a recording-level split is used and session overlap is reported. Training uses train rows for scale and references, validation rows for checkpoint and thresholds, and does not embed or score test rows.

`known-user-test-v1` audits the saved manifest for duplicate or overlapping IDs, profile ownership, coverage, and session claims. It fits a new baseline on the same training rows, calibrates both models on the same validation rows, then scores identical held-out recording and claimed-profile pairs. FAR, FRR, precision, recall, confusion counts, and ROC points come from these saved attempts. Pooled ROC thresholds use each attempt's similarity minus its profile threshold. AUC and EER require at least 20 genuine and 20 impostor test attempts; smaller curves are exploratory. The reference-count study varies training reference count while keeping the encoder and scaler fixed.

Saved experiments include data and source fingerprints, feature and model versions, training settings, seed, PyTorch version, split IDs, thresholds, and Git revision. A repeat evaluation with the same dataset, checkpoint, and evaluation code reuses the saved run rather than reopening the test partition. `app.report_cli` renders tables and figures from that saved record. Reproducibility is scoped to this local CPU/software environment; exact floating-point behavior across hardware and package versions is not guaranteed.
