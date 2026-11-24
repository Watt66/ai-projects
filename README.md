# Applied IT, networking, and automation projects

Practical learning projects by David Gitau Maina, focused on IT support, networking, Python, and later AI-assisted workflows.

| Project | What it demonstrates | Status |
| --- | --- | --- |
| [Network Health Analyzer](network-health-analyzer/) | CSV validation, shared-WAN calculations, troubleshooting evidence, HTML/JSON reports, and automated tests | Working starter using synthetic data |
| `ai-learning-assistant.zip` | Earlier learning-assistant archive | Legacy material; not validated by the network analyzer checks |

The network analyzer is rule-based Python automation. AI features will be described separately when implemented and evaluated. Read each project's limitations and record personal extensions in its learning log.

## Start here

```bash
cd network-health-analyzer
python analyze.py data/demo.csv --output report.html --json report.json
python -m unittest discover -s tests -v
```

Requires Python 3.10+. The network analyzer has no third-party dependencies.

See [LICENSE](LICENSE) for the repository license.
