SecondBrain DeepSeek Integration TODO

- [x] Verify prerequisites and environment (venv311, CLI health/status)
- [ ] Set up DeepSeek Docker service (blocked: upstream repo missing DeepSeek-OCR sources)
- [ ] Download model and health-check API on port 8001
- [x] Implement DeepSeek OCR module (HTTP client)
- [x] Integrate engine selection in pipeline (openai|deepseek|hybrid)
- [x] Update local config with DeepSeek options (engine=hybrid, ratio=0.1)
- [x] Create side-by-side test script (`test_engines.py`)
- [x] Add MCP server skeleton + CLI command (`mcp_server`)
- [x] Run DB migration for new columns (ocr_engine, compression_ratio)
- [ ] Perform gradual hybrid rollout (needs DeepSeek service running)
- [x] Add monitoring script (`monitor_ocr.py`)
- [ ] Document rollback and test restart
- [ ] Tick verification checklist in runbook

Notes

- Docker build currently fails due to missing `DeepSeek-OCR/...` directories in the upstream repo. Once fixed, rebuild and re-run health check.
- On macOS without NVIDIA GPU, the provided Dockerfile may require CPU-compatible adjustments.
