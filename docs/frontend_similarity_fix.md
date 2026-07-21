# Frontend and similarity correction — v0.1.5

## Error corrected

```text
IndexError: index 9 is out of bounds for axis 1 with size 9
```

Some fingerprint fields were completely empty in the eligible historical
windows. Scikit-learn removed those fields during median imputation, while the
explanation loop retained the original feature list.

Version 0.1.5:

- excludes empty and constant historical features before similarity;
- preserves matrix dimensions explicitly;
- validates the transformed feature count;
- handles Mahalanobis covariance safely;
- converts historical sentinel values such as `-99` to null;
- prevents invalid magnitudes from entering charts and energy calculations;
- aggregates long catalogues by year rather than drawing monthly data across centuries.

## Required rebuild

Because old Gold fingerprints may contain sentinel-derived values, rebuild
Silver and Gold after applying the patch:

```cmd
python -m src.pipeline clean-derived
python -m src.pipeline build-silver
python -m src.pipeline build-gold
python -m src.pipeline report
python -m src.pipeline data-status
```
