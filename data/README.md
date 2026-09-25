# data/

**No orbital data is committed here, on purpose.** The catalogue changes every few hours and is U.S. Space
Command's to distribute, so the repository carries none of it.

- **The orbital catalogue** is staged in Cloud Storage by `notebooks/demo_90_stage_catalog.ipynb`, run by a
  maintainer with a Space-Track account:
  `gs://class-demo/a4i-2026/demo-orbital-conjunction/catalog/<snapshot>/`. The kickoff pins snapshot
  `20260925T0137Z`, so the numbers on stage are the same in every city.
- **The Cymbal Orbital fleet** is defined in section 8 of `notebooks/demo_01_load_explore.ipynb`—twelve
  fictional satellites, written as orbital elements from a handful of stated parameters, so you can see
  exactly how an orbit is specified.
- **The tables** land in `<your-project>.a4i_orbit`: `catalog`, `satcat`, `fleet`, `conjunctions`,
  `snapshot_info`. `bash scripts/load.sh` restores them without the notebook.

*Orbital data: U.S. Space Command, via Space-Track.org; satellite catalogue via CelesTrak (celestrak.org).*
