from galgame_character_skills.application.compression_executor import run_compression_pipeline


def test_run_compression_pipeline_uses_llm_compress_when_mode_llm():
    calls = {"llm": 0, "fallback": 0}

    def llm_compress(target_budget_tokens):
        calls["llm"] += 1
        assert target_budget_tokens == 8000
        return "llm-compressed"

    def fallback_compress(target_budget_tokens):
        calls["fallback"] += 1
        return f"fallback-{target_budget_tokens}"

    compressed, used, context_limit, context_limit_tokens = run_compression_pipeline(
        runtime=object(),
        model_name="m",
        compression_mode="llm",
        force_no_compression=False,
        raw_estimated_tokens=12000,
        policy={
            "context_limit": 10000,
            "context_limit_tokens": 8000,
            "should_compress": True,
            "force_exceeds_limit": False,
        },
        llm_compress=llm_compress,
        fallback_compress=fallback_compress,
    )

    assert compressed == "llm-compressed"
    assert used is True
    assert context_limit == 10000
    assert context_limit_tokens == 8000
    assert calls == {"llm": 1, "fallback": 0}


def test_run_compression_pipeline_uses_fallback_when_non_llm_mode():
    calls = {"llm": 0, "fallback": 0}

    def llm_compress(target_budget_tokens):
        calls["llm"] += 1
        return f"llm-{target_budget_tokens}"

    def fallback_compress(target_budget_tokens):
        calls["fallback"] += 1
        assert target_budget_tokens == 6000
        return "fallback-compressed"

    compressed, used, _, _ = run_compression_pipeline(
        runtime=object(),
        model_name="m",
        compression_mode="original",
        force_no_compression=False,
        raw_estimated_tokens=9000,
        policy={
            "context_limit": 9000,
            "context_limit_tokens": 6000,
            "should_compress": True,
            "force_exceeds_limit": False,
        },
        llm_compress=llm_compress,
        fallback_compress=fallback_compress,
    )

    assert compressed == "fallback-compressed"
    assert used is True
    assert calls == {"llm": 0, "fallback": 1}


def test_run_compression_pipeline_returns_no_compress_result():
    calls = {"llm": 0, "fallback": 0}

    def llm_compress(target_budget_tokens):
        calls["llm"] += 1
        return f"llm-{target_budget_tokens}"

    def fallback_compress(target_budget_tokens):
        calls["fallback"] += 1
        return f"fallback-{target_budget_tokens}"

    compressed, used, context_limit, context_limit_tokens = run_compression_pipeline(
        runtime=object(),
        model_name="m",
        compression_mode="llm",
        force_no_compression=True,
        raw_estimated_tokens=10000,
        policy={
            "context_limit": 9000,
            "context_limit_tokens": 7000,
            "should_compress": False,
            "force_exceeds_limit": True,
        },
        llm_compress=llm_compress,
        fallback_compress=fallback_compress,
    )

    assert compressed is None
    assert used is False
    assert context_limit == 9000
    assert context_limit_tokens == 7000
    assert calls == {"llm": 0, "fallback": 0}
