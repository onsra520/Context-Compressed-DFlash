import json
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"

def load_notebook(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_source(cell):
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return src

def test_notebooks_are_valid_json():
    for nb_name in ["01_fetch_and_process_datasets.ipynb", 
                    "02_run_three_version_benchmark.ipynb", 
                    "03_compare_benchmark_charts.ipynb"]:
        nb = load_notebook(NB_DIR / nb_name)
        assert nb.get("nbformat") >= 4

def test_titles_and_config_vars():
    nb1 = load_notebook(NB_DIR / "01_fetch_and_process_datasets.ipynb")
    code_content_1 = "".join([get_source(c) for c in nb1["cells"] if c["cell_type"] == "code"])
    assert "ALLOW_NETWORK_FETCH =" not in code_content_1, "No ALLOW_NETWORK_FETCH=False gate allowed"
    
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    code_content_2 = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "code"])
    assert "DATASET =" in code_content_2
    assert "RUN_REAL_MODELS = False" not in code_content_2, "No RUN_REAL_MODELS=False gate allowed"
    assert "CCDF_NOTEBOOK_TEST_MODE" in code_content_2, "Test mode override should exist"


def test_no_hardcoded_paths():
    for nb_name in ["01_fetch_and_process_datasets.ipynb", 
                    "02_run_three_version_benchmark.ipynb", 
                    "03_compare_benchmark_charts.ipynb"]:
        nb = load_notebook(NB_DIR / nb_name)
        text = json.dumps(nb)
        assert "/home/quyseggs" not in text

def test_nb2_references_t112a_api():
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    code = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "code"])
    assert "from ccdf.demo import DemoRunner" in code

def test_nb2_contains_condition_ids():
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    code = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "code"])
    assert "baseline_ar" in code
    assert "dflash_r1" in code
    assert "cc_dflash_r2" in code

def test_nb2_writes_to_notebook_demo():
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    code = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "code"])
    assert "results/charts/notebook_demo" in code

def test_nb3_no_generation_models():
    nb3 = load_notebook(NB_DIR / "03_compare_benchmark_charts.ipynb")
    code = "".join([get_source(c) for c in nb3["cells"] if c["cell_type"] == "code"])
    assert "AutoModelForCausalLM" not in code
    assert "GENERATE_CHARTS = True" not in code

def test_notebook_generator_exists():
    assert (ROOT / "notebooks" / "notebook_setup.py").exists()

def test_output_paths_resolve_to_root():
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    code2 = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "code"])
    assert "results/charts/notebook_demo" in code2

    nb3 = load_notebook(NB_DIR / "03_compare_benchmark_charts.ipynb")
    code3 = "".join([get_source(c) for c in nb3["cells"] if c["cell_type"] == "code"])
    assert "results/charts/notebook_demo" in code3

def test_nb3_no_models_loaded():
    nb3 = load_notebook(NB_DIR / "03_compare_benchmark_charts.ipynb")
    code = "".join([get_source(c) for c in nb3["cells"] if c["cell_type"] == "code"])
    assert "DemoRunner" not in code
    assert "load_target" not in code
    assert "LLMLingua" not in code

def test_nb3_validates_schema():
    # Schema validation is in charting helper
    charting = (ROOT / "src/ccdf/demo/charting.py").read_text(encoding="utf-8")
    assert "cc_dflash_demo_v1" in charting

def test_chart_helpers_with_fixture(tmp_path):
    from ccdf.demo.charting import generate_charts_for_dataset
    csv_content = """schema_version,run_id,source_type,dataset,split,fixture_id,condition,condition_display_name,prompt_profile,prompt,reference_answer,generated_text,original_input_tokens,compressed_input_tokens,compression_ratio,output_tokens,t_compress_ms,t_prefill_ms,t_generation_ms,t_e2e_ms,generation_tok_s,e2e_tok_s,peak_vram_gib,finish_reason,evaluation_status,numeric_match,normalized_overlap,ok,error_type,error_message
cc_dflash_demo_v1,123,dataset,gsm8k,test,1,baseline_ar,Baseline-AR,raw,prompt,ref,gen,10,,,5,0.0,10.0,10.0,20.0,1.0,1.0,5.0,,not_evaluated,True,,True,,
cc_dflash_demo_v1,123,dataset,gsm8k,test,1,dflash_r1,DFlash-R1,raw,prompt,ref,gen,10,,,5,0.0,10.0,10.0,20.0,1.0,1.0,5.0,,not_evaluated,True,,True,,
cc_dflash_demo_v1,123,dataset,gsm8k,test,1,cc_dflash_r2,CC-DFlash-R2,raw,prompt,ref,gen,10,5,0.5,5,10.0,10.0,10.0,30.0,1.0,1.0,5.0,,not_evaluated,True,,True,,
"""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)
    charts = list(generate_charts_for_dataset(str(csv_file), "gsm8k"))
    assert len(charts) > 0
    assert any("average_e2e_latency.png" == name for name, fig in charts)

def test_qmsum_caveat():
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    md = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "markdown"])
    assert "Semantic correctness is not claimed" in md

def test_no_fabricated_rows():
    for nb_name in ["01_fetch_and_process_datasets.ipynb", 
                    "02_run_three_version_benchmark.ipynb", 
                    "03_compare_benchmark_charts.ipynb"]:
        nb = load_notebook(NB_DIR / nb_name)
        text = json.dumps(nb).lower()
        # Ensure there's no hardcoded CSV data for benchmark values
        assert "cc_dflash_demo_v1,123," not in text



def test_t112b_r2_requirements():
    nb2 = load_notebook(NB_DIR / "02_run_three_version_benchmark.ipynb")
    code2 = "".join([get_source(c) for c in nb2["cells"] if c["cell_type"] == "code"])
    assert "RUN_REAL_MODELS =" not in code2
    assert "RESUME = True" not in code2
    assert 'strftime("%Y%m%dT%H%M%SZ")' in code2
    assert "res.response.generated_text" in code2
    assert "req.prompt" in code2
    assert "out_jsonl" in code2 and "latest_run.json" in code2
    
    nb3 = load_notebook(NB_DIR / "03_compare_benchmark_charts.ipynb")
    code3 = "".join([get_source(c) for c in nb3["cells"] if c["cell_type"] == "code"])
    assert "latest_run.json" in code3
    assert "display(figure)" in code3
    assert "generate_charts_for_dataset" in code3
