# Test guide — MEMÓRIA v2.0

After applying the patch:

```cmd
.venv\Scripts\activate
python -m pip install --upgrade -e .
python -m src.pipeline clean-derived
python -m src.pipeline build-silver
build_gold_all.cmd
python -m src.pipeline tectonic-status --window 90
python -m streamlit cache clear
python -m streamlit run app\streamlit_app.py
```

The new pages are:

- **Inteligência tectónica** — anomaly consensus, b-value, migration, regimes, optional multimodal evidence and evidence graph.
- **Model Arena** — reproducible benchmark including ETAS-lite.
- **Scientific Council** — agentic peer-review layer using the existing Mistral key.

Optional data schemas:

### GNSS

```csv
date,station,latitude,longitude,velocity_mm_year,strain
```

### InSAR

```csv
date,latitude,longitude,los_displacement_mm,velocity_mm_year
```

### Faults

Provide a scientifically reviewed GeoJSON `FeatureCollection` of line geometries at `config/faults.geojson`.
