# Metric protocol

## Boundary agreement

The historical noise script requires exact pixel overlap between boundaries. This is useful as a strict diagnostic but over-penalizes a small registration or discretization shift. MonoGrowLab therefore reports boundary precision, recall, and F1 at tolerance 0 and at explicitly stated pixel tolerances.

A candidate boundary pixel is matched when it lies inside a morphological dilation of the reference boundary. Recall is computed symmetrically by matching reference pixels against the dilated candidate boundary. Connectivity and tolerance are recorded with every result.

## Partition agreement

Adjusted Rand index and variation of information are label-invariant: renumbering regions must not change the score. Variation of information is stored as split, merge, and total components so that over-segmentation and under-segmentation are not hidden inside one scalar.

## Correctness fixtures

The initial tests cover identical maps, a pure label permutation, a one-pixel boundary shift, empty-boundary conventions, and invalid shape or tolerance inputs. These are correctness tests, not evidence of scientific performance.

## Interpretation rule

No algorithm is declared better from one metric or one synthetic image. Quality, robustness, runtime, coverage, and region-count behavior must be considered jointly on documented datasets.

