from scripts.analyze_task68_gsm8k_final_settings import synthesize_final_settings


def test_synthesis_freezes_settings_and_recommends_n30_gate():
    summaries = {
        "task60_mnt256": {
            "comparisons": {
                "LLMLingua-AR-R2": {"task60_numeric_extraction_rate": 0.8},
                "CC-DFlash-R2": {"task60_numeric_extraction_rate": 0.8},
            }
        },
        "task61b_keep_rate67": {
            "changed_outcome_counts": {
                "FAIL_TO_PASS": 2,
                "PASS_TO_FAIL": 2,
            }
        },
        "task62_k67_triage": {
            "direct_evidence_k67_helped_compression_loss": False,
            "direct_evidence_k67_hurt_or_instability": True,
            "test_keep_rate_80_next": "NO",
        },
        "task63_n30_mnt256": {
            "artifacts": {
                "task63_n30": {
                    "LLMLingua-AR-R2": {
                        "rows": 30,
                        "numeric_extraction_match_count": 22,
                        "numeric_extraction_rate": 0.733333,
                        "hit_token_cap_count": 5,
                    },
                    "CC-DFlash-R2": {
                        "rows": 30,
                        "numeric_extraction_match_count": 23,
                        "numeric_extraction_rate": 0.766667,
                        "hit_token_cap_count": 5,
                    },
                }
            },
            "comparisons": {
                "LLMLingua-AR-R2": {
                    "task63_numeric_extraction_rate": 0.733333,
                    "classification": "STABLE",
                },
                "CC-DFlash-R2": {
                    "task63_numeric_extraction_rate": 0.766667,
                    "classification": "STABLE",
                },
            }
        },
        "task66_mnt384": {
            "task65_latency_appears_noisy_overall": True,
            "artifacts": {
                "task66_mnt384_rerun": {
                    "LLMLingua-AR-R2": {
                        "numeric_extraction_match_count": 24,
                        "rows": 30,
                        "hit_token_cap_count": 3,
                    },
                    "CC-DFlash-R2": {
                        "numeric_extraction_match_count": 24,
                        "rows": 30,
                        "hit_token_cap_count": 3,
                    },
                }
            },
        },
        "task67_failure_triage": {
            "overall": {
                "label_counts": {
                    "REASONING_FAIL": 6,
                    "TRUNCATION_REMAINING": 6,
                    "COMPRESSION_LOSS_POSSIBLE": 0,
                    "ANSWER_FORMAT_OR_EXTRACTION_ISSUE": 0,
                }
            },
            "decision": {
                "mnt512_justification": "NOT_JUSTIFIED",
            },
        },
    }

    summary, table = synthesize_final_settings(summaries)

    assert summary["final_settings"]["speed_oriented"]["max_new_tokens"] == 256
    assert summary["final_settings"]["quality_oriented"]["max_new_tokens"] == 384
    assert summary["final_settings"]["speed_oriented"]["keep_rate"] == 0.5
    assert summary["rejections"]["keep_rate_0_67"]["decision"] == "REJECT_AS_DEFAULT"
    assert summary["rejections"]["keep_rate_0_75_0_80"]["decision"] == "DEFER"
    assert summary["rejections"]["max_new_tokens_512"]["decision"] == "DEFER"
    assert summary["next_real_run_plan"]["selected_option"] == "Option C"
    assert summary["n100_gate"]["status"] == "NOT_NEXT"
    assert any(row["setting"] == "quality_oriented" for row in table)
    assert any(
        row["setting"] == "speed_oriented"
        and row["condition"] == "LLMLingua-AR-R2"
        and row["numeric_matches"] == 22
        and row["cap_hits"] == 5
        for row in table
    )
